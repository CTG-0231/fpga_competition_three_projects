"""Exercise exported HLS top RTL through AXI-Lite and byte-addressed AXI memory.

This independent, bounded model avoids the official co-simulator's AXI VIP.
It is a functional test, not an AXI compliance, timing or board validation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def sat(value):
    return max(-32768, min(32767, value))


def madd(acc, a, b):
    # AP_RND: round nearest, ties toward +infinity; AP_SAT on assignment.
    return sat((acc * 1024 + a * b + 512) // 1024)


def relu(value):
    return max(0, min(6144, value))


def pack_channels(values, channels, pixels):
    return [values[(g * 4 + lane) * pixels + pix]
            for g in range(channels // 4) for pix in range(pixels) for lane in range(4)]


def make_cases(kernel, extended=False):
    cases = []
    if kernel == "shortcut":
        a = [32767, -32768, 32760, -32760, 512, -512, 1, -1, 30000, -30000, 0, 1024, 200, -200, 16384, -16384]
        b = [1, -1, 100, -100, -1, 1, -1, 1, 30000, -30000, 0, -1024, -300, 300, 16384, -16384]
        cases.append(dict(name="signed_saturation", arrays={0x1000: a, 0x2000: b}, output=0x3000,
                          expected=[sat(x + y) for x, y in zip(a, b)],
                          registers={0x10: 0x1000, 0x18: 0x2000, 0x20: 0x3000, 0x28: 16}))
    elif kernel == "fc":
        inp = [((c * 179 + p * 67) % 4001) - 2000 for c in range(1280) for p in range(49)]
        weights = [((m * 113 + c * 17) % 2049) - 1024 for m in range(6) for c in range(1280)]
        bias = [32760, -32760, 512, -512, 0, 6144]
        averaged = []
        for c in range(1280):
            row = inp[c * 49:(c + 1) * 49]
            p1 = [sat(row[t] + row[t + 24]) for t in range(24)]
            p2 = [sat(p1[t] + p1[t + 12]) for t in range(12)]
            p3 = [sat(p2[t] + p2[t + 6]) for t in range(6)]
            p4 = [sat(p3[t] + p3[t + 3]) for t in range(3)]
            p5 = [sat(p4[0] + p4[1]), sat(p4[2] + row[48])]
            averaged.append(sat(((p5[0] + p5[1]) * 21 + 512) // 1024))
        expected = []
        for m in range(6):
            total = bias[m]
            for c in range(1280):
                total = madd(total, averaged[c], weights[m * 1280 + c])
            expected.append(total)
        cases.append(dict(name="six_outputs_q10", arrays={0x1000: pack_channels(inp, 1280, 49), 0x30000: weights, 0x40000: bias},
                          output=0x50000, expected=expected,
                          registers={0x10: 0x1000, 0x18: 0x30000, 0x20: 0x40000, 0x28: 0x50000}))
    elif kernel == "conv":
        inp = [((c * 131 + p * 11) % 2049) - 1024 for c in range(3) for p in range(224 * 224)]
        weights = [((m * 13 + n * 7 + k * 5) % 65) - 32 for m in range(32) for n in range(3) for k in range(9)]
        bias = [(-512, 0, 512, 6140, 8192, -8192, 32760, -32760)[m % 8] for m in range(32)]
        planar = [0] * (32 * 112 * 112)
        for m in range(32):
            for r in range(112):
                for c in range(112):
                    total = bias[m]
                    for kx in range(3):
                        for ky in range(3):
                            rr, cc = 2 * r + kx - 1, 2 * c + ky - 1
                            for n in range(3):
                                value = inp[n * 224 * 224 + rr * 224 + cc] if 0 <= rr < 224 and 0 <= cc < 224 else 0
                                total = madd(total, value, weights[m * 27 + n * 9 + kx * 3 + ky])
                    planar[m * 112 * 112 + r * 112 + c] = relu(total)
        cases.append(dict(name="rgb_padding_relu6_q10", arrays={0x1000: inp, 0x60000: weights, 0x61000: bias},
                          output=0x80000, expected=pack_channels(planar, 32, 112 * 112),
                          registers={0x10: 0x1000, 0x18: 0x1000, 0x20: 0x1000, 0x28: 0x60000, 0x30: 0x61000, 0x38: 0x80000}))
    elif kernel == "pwdwconv":
        ch, cout, size = 16, 24, 7
        inp = [((n * 233 + p * 37) % 4097) - 2048 for n in range(ch) for p in range(size * size)]
        weights = [((m * 197 + n * 113) % 4097) - 2048 for m in range(32) for n in range(ch)]
        bias = [32760, -32760, 512, -512, 0, 6140, 8192, -8192] * 4
        for act in (0, 1):
            planar = []
            for m in range(cout):
                for p in range(size * size):
                    total = bias[m]
                    for n in range(ch):
                        total = madd(total, inp[n * size * size + p], weights[m * ch + n])
                    planar.append(relu(total) if act else total)
            cases.append(dict(name="pointwise_act%d_q10" % act,
                              arrays={0x1000: pack_channels(inp, ch, size * size), 0x20000: weights, 0x30000: bias},
                              output=0x40000, expected=pack_channels(planar, cout, size * size),
                              registers={0x10: 0x1000, 0x18: 0x20000, 0x20: 0x20000, 0x28: 0x40000,
                                         0x30: 0x30000, 0x38: 0x30000, 0x40: ch, 0x48: cout, 0x50: 1, 0x58: size, 0x60: act, 0x68: 1}))
        for stride, size in ((1, 7), (2, 14)):
            pixels, output_size = size * size, size // stride
            inp = [((n * 131 + p * 17) % 2049) - 1024 for n in range(ch) for p in range(pixels)]
            weights = [((n * 13 + k * 7) % 1025) - 512 for n in range(ch) for k in range(9)]
            bias = [(-512, 0, 512, 6140, 8192, -8192, 32760, -32760)[n % 8] for n in range(ch)]
            planar = []
            for n in range(ch):
                for r in range(output_size):
                    for c in range(output_size):
                        total = bias[n]
                        for kx in range(3):
                            for ky in range(3):
                                rr, cc = r * stride + kx - 1, c * stride + ky - 1
                                value = inp[n * pixels + rr * size + cc] if 0 <= rr < size and 0 <= cc < size else 0
                                total = madd(total, value, weights[n * 9 + kx * 3 + ky])
                        planar.append(relu(total))
            cases.append(dict(name="depthwise_stride%d_q10" % stride,
                              arrays={0x1000: pack_channels(inp, ch, pixels), 0x20000: weights, 0x30000: bias},
                              output=0x40000, expected=pack_channels(planar, ch, output_size * output_size),
                              registers={0x10: 0x1000, 0x18: 0x1000, 0x20: 0x40000, 0x28: 0x40000,
                                         0x30: 0x20000, 0x38: 0x30000, 0x40: ch, 0x48: ch, 0x50: stride,
                                         0x58: size, 0x60: 1, 0x68: 0}))
        # Different bias values in every channel catch missing/non-first rows.
        for cin, cout in ([(16, 96), (4, 1280)] if extended else [(16, 96)]):
            size, pixels = 7, 49
            inp = [((n * 233 + p * 37) % 4097) - 2048 for n in range(cin) for p in range(pixels)]
            weights = [((m * 197 + n * 113) % 4097) - 2048 for m in range(cout) for n in range(cin)]
            bias = [((m * 733 + 17) % 60001) - 30000 for m in range(cout)]
            planar = []
            for m in range(cout):
                for p in range(pixels):
                    total = bias[m]
                    for n in range(cin):
                        total = madd(total, inp[n * pixels + p], weights[m * cin + n])
                    planar.append(total)
            bias_addr, out_addr = (0x100000, 0x120000) if cout == 1280 else (0x30000, 0x40000)
            cases.append(dict(name="pointwise_%d_to_%d_multirow_q10" % (cin, cout),
                              arrays={0x1000: pack_channels(inp, cin, pixels), 0x20000: weights, bias_addr: bias},
                              output=out_addr, expected=pack_channels(planar, cout, pixels),
                              registers={0x10: 0x1000, 0x18: 0x20000, 0x20: 0x20000, 0x28: out_addr,
                                         0x30: bias_addr, 0x38: bias_addr, 0x40: cin, 0x48: cout, 0x50: 1,
                                         0x58: size, 0x60: 0, 0x68: 1}))
        for channels in ([32, 960] if extended else [32]):
            pixels = 49
            inp = [((n * 131 + p * 17) % 2049) - 1024 for n in range(channels) for p in range(pixels)]
            weights = [((n * 13 + k * 7) % 1025) - 512 for n in range(channels) for k in range(9)]
            bias = [((n * 733 + 17) % 60001) - 30000 for n in range(channels)]
            planar = []
            for n in range(channels):
                for r in range(7):
                    for c in range(7):
                        total = bias[n]
                        for kx in range(3):
                            for ky in range(3):
                                rr, cc = r + kx - 1, c + ky - 1
                                value = inp[n * pixels + rr * 7 + cc] if 0 <= rr < 7 and 0 <= cc < 7 else 0
                                total = madd(total, value, weights[n * 9 + kx * 3 + ky])
                        planar.append(relu(total))
            cases.append(dict(name="depthwise_%d_multirow_q10" % channels,
                              arrays={0x1000: pack_channels(inp, channels, pixels), 0x20000: weights, 0x30000: bias},
                              output=0x40000, expected=pack_channels(planar, channels, pixels),
                              registers={0x10: 0x1000, 0x18: 0x1000, 0x20: 0x40000, 0x28: 0x40000,
                                         0x30: 0x20000, 0x38: 0x30000, 0x40: channels, 0x48: channels,
                                         0x50: 1, 0x58: 7, 0x60: 1, 0x68: 0}))
    else:
        raise ValueError(kernel)
    return cases


def get_ports(component):
    root = ET.parse(component).getroot()
    result = {}
    for port in root.findall('./{*}model/{*}ports/{*}port'):
        name, wire = port.findtext('{*}name'), port.find('{*}wire')
        left, right = wire.findtext('{*}vector/{*}left'), wire.findtext('{*}vector/{*}right')
        result[name] = (wire.findtext('{*}direction'), 1 if left is None else abs(int(left) - int(right)) + 1)
    return result


def axi_model(bus, width):
    b, n = bus, width // 8
    return f'''
reg {b}_read_active=0, {b}_write_active=0;
reg [31:0] {b}_read_addr, {b}_write_addr;
reg [7:0] {b}_read_left, {b}_write_left;
reg [2:0] {b}_read_size, {b}_write_size;
reg [1:0] {b}_read_burst, {b}_write_burst;
reg {b}_read_id, {b}_write_id;
integer {b}_lane;
always_comb begin
 {b}_ARREADY = !{b}_read_active;
 {b}_AWREADY = !{b}_write_active && !{b}_BVALID;
 {b}_WREADY = {b}_write_active;
 {b}_RVALID = {b}_read_active;
 {b}_RLAST = {b}_read_left == 0;
 {b}_RID = {b}_read_id;
 {b}_RRESP = 0; {b}_RUSER = 0; {b}_BUSER = 0; {b}_BRESP = 0;
end
integer {b}_write_lane;
always @(posedge ap_clk) begin
 if (!ap_rst_n) begin
  {b}_read_active<=0; {b}_write_active<=0; {b}_BVALID<=0; {b}_BID<=0;
 end else begin
  if ({b}_ARVALID && {b}_ARREADY) begin
   if ({b}_ARID !== 1'b0) $fatal(1,"Nonzero/unknown ARID {b}");
   if ({b}_ARADDR >= MEMSIZE || (1 << {b}_ARSIZE) > {n} || {b}_ARBURST > 1) $fatal(1,"Unsupported/read address {b}");
   {b}_read_active<=1; {b}_read_addr<={b}_ARADDR; {b}_read_left<={b}_ARLEN;
   {b}_read_size<={b}_ARSIZE; {b}_read_id<={b}_ARID; {b}_read_burst<={b}_ARBURST;
   for ({b}_lane=0; {b}_lane<{n}; {b}_lane={b}_lane+1)
    {b}_RDATA[{b}_lane*8 +: 8] <= mem[({b}_ARADDR & ~({n}-1))+{b}_lane];
  end
  if ({b}_RVALID && {b}_RREADY) begin
   read_beats=read_beats+1;
   if ({b}_read_addr >= MEMSIZE) $fatal(1,"Read outside memory {b}");
   if ({b}_read_left==0) {b}_read_active<=0;
   else begin
    {b}_read_left<={b}_read_left-1;
    if ({b}_read_burst==1) {b}_read_addr<={b}_read_addr+(1 << {b}_read_size);
    for ({b}_lane=0; {b}_lane<{n}; {b}_lane={b}_lane+1)
     {b}_RDATA[{b}_lane*8 +: 8] <= mem[((({b}_read_burst==1 ? {b}_read_addr+(1 << {b}_read_size) : {b}_read_addr)) & ~({n}-1))+{b}_lane];
   end
  end
  if ({b}_AWVALID && {b}_AWREADY) begin
   if ({b}_AWID !== 1'b0) $fatal(1,"Nonzero/unknown AWID {b}");
   if ({b}_AWADDR >= MEMSIZE || (1 << {b}_AWSIZE) > {n} || {b}_AWBURST > 1) $fatal(1,"Unsupported/write address {b}");
   {b}_write_active<=1; {b}_write_addr<={b}_AWADDR; {b}_write_left<={b}_AWLEN;
   {b}_write_size<={b}_AWSIZE; {b}_write_id<={b}_AWID; {b}_write_burst<={b}_AWBURST;
  end
  if ({b}_WVALID && {b}_WREADY) begin
   if ({b}_WID !== 1'b0) $fatal(1,"Nonzero/unknown WID {b}");
   write_beats=write_beats+1;
   if ({b}_WLAST !== ({b}_write_left==0)) $fatal(1,"WLAST mismatch {b}");
   if ({b}_write_addr >= MEMSIZE) $fatal(1,"Write outside memory {b}");
   for ({b}_write_lane=0; {b}_write_lane<{n}; {b}_write_lane={b}_write_lane+1)
    if ({b}_WSTRB[{b}_write_lane]) mem[({b}_write_addr & ~({n}-1))+{b}_write_lane] <= {b}_WDATA[{b}_write_lane*8 +: 8];
   if ({b}_write_left==0) begin
    {b}_write_active<=0; {b}_BVALID<=1; {b}_BID<={b}_write_id;
   end else begin
    {b}_write_left<={b}_write_left-1;
    if ({b}_write_burst==1) {b}_write_addr<={b}_write_addr+(1 << {b}_write_size);
   end
  end
  if ({b}_BVALID && {b}_BREADY) {b}_BVALID<=0;
 end
end
'''


HOST = r'''
task axil_write(input [31:0] address, input [31:0] value);
 reg aw, wd;
 begin
  aw=0; wd=0;
  @(negedge ap_clk);
  s_axi_CTRL_AWADDR=address; s_axi_CTRL_AWVALID=1;
  s_axi_CTRL_WDATA=value; s_axi_CTRL_WSTRB=15; s_axi_CTRL_WVALID=1;
  while (!aw || !wd) begin
   @(posedge ap_clk);
   if (s_axi_CTRL_AWREADY) aw=1;
   if (s_axi_CTRL_WREADY) wd=1;
   @(negedge ap_clk);
   if (aw) s_axi_CTRL_AWVALID=0;
   if (wd) s_axi_CTRL_WVALID=0;
  end
  s_axi_CTRL_BREADY=1;
  @(posedge ap_clk);
  while (!s_axi_CTRL_BVALID) @(posedge ap_clk);
  if (s_axi_CTRL_BRESP != 0) $fatal(1,"AXI-Lite BRESP");
  @(negedge ap_clk); s_axi_CTRL_BREADY=0;
 end
endtask
task axil_read(input [31:0] address, output [31:0] value);
 begin
  @(negedge ap_clk); s_axi_CTRL_ARADDR=address; s_axi_CTRL_ARVALID=1; s_axi_CTRL_RREADY=1;
  @(posedge ap_clk);
  while (!s_axi_CTRL_ARREADY) @(posedge ap_clk);
  @(negedge ap_clk); s_axi_CTRL_ARVALID=0;
  @(posedge ap_clk);
  while (!s_axi_CTRL_RVALID) @(posedge ap_clk);
  value=s_axi_CTRL_RDATA;
  if (s_axi_CTRL_RRESP != 0) $fatal(1,"AXI-Lite RRESP");
  @(negedge ap_clk); s_axi_CTRL_RREADY=0;
 end
endtask
'''


def generate(kernel, ip, output, extended=False):
    ports = get_ports(ip / "component.xml")
    if any(n.startswith('s_axi_control') for n in ports):
        raise ValueError("Unexpected second control bank")
    cases = make_cases(kernel, extended)
    declarations = []
    for name, (direction, width) in ports.items():
        vector = ("[%d:0] " % (width - 1)) if width > 1 else ""
        declarations.append(("reg " if direction == "in" else "wire ") + vector + name + ("=0;" if direction == "in" else ";"))
    buses = sorted({name.rsplit('_', 1)[0] for name in ports if name.startswith('m_axi_') and name.endswith('_ARADDR')})
    # AXI memory outputs are DUT inputs; a single model drives each one.
    models = [axi_model(bus, ports[bus + '_RDATA'][1]) for bus in buses]
    top = ['`timescale 1ns/1ps', 'module tb;', 'localparam MEMSIZE=2097152;',
           'reg [7:0] mem[0:MEMSIZE-1];', 'reg [15:0] expected[0:401407];',
           'integer read_beats=0, write_beats=0, i, poll, cycles=0, checks=0;', 'reg [31:0] status;',
           '\n'.join(declarations), 'always #2.5 ap_clk=~ap_clk;',
           'always @(posedge ap_clk) begin cycles=cycles+1; if(cycles>10000000) $fatal(1,"cycle timeout"); end',
           kernel + ' dut(' + ','.join('.%s(%s)' % (name, name) for name in ports) + ');',
           '\n'.join(models), HOST, 'initial begin']
    case_meta = []
    for index, case in enumerate(cases):
        mem_path = output / ('memory_%d.hex' % index)
        with mem_path.open('w') as f:
            for address, values in case['arrays'].items():
                f.write('@%x\n' % address)
                for value in values:
                    f.write('%02x\n%02x\n' % (value & 255, (value >> 8) & 255))
        expected_path = output / ('expected_%d.hex' % index)
        expected_path.write_text(''.join('%04x\n' % (v & 65535) for v in case['expected']))
        top += ['ap_rst_n=0; repeat(10) @(negedge ap_clk);',
                'for(i=0;i<MEMSIZE;i=i+1) mem[i]=0;',
                '$readmemh("%s",mem);' % mem_path.name,
                '$readmemh("%s",expected,0,%d);' % (expected_path.name, len(case['expected']) - 1),
                'ap_rst_n=1; repeat(10) @(negedge ap_clk);']
        top += ['axil_write(32\'h%x,32\'h%x);' % (offset, value) for offset, value in case['registers'].items()]
        top += ['axil_write(0,1);', 'status=0; poll=0;',
                'while ((status & 2)==0) begin axil_read(0,status); poll=poll+1; if(poll>2000000) begin $display("TIMEOUT ctrl=%h reads=%0d writes=%0d",status,read_beats,write_beats); $fatal(1,"AP_DONE timeout"); end end',
                'for(i=0;i<%d;i=i+1) begin' % len(case['expected']),
                ' if ({mem[32\'h%x+2*i+1],mem[32\'h%x+2*i]} !== expected[i]) begin' % (case['output'], case['output']),
                '  $display("MISMATCH case=%s index=%%0d got=%%h expected=%%h", i, {mem[32\'h%x+2*i+1],mem[32\'h%x+2*i]},expected[i]);' % (case['name'], case['output'], case['output']),
                '  $fatal(1,"Q10 mismatch"); end', ' checks=checks+1;', 'end',
                '$display("CASE_PASS %s values=%d cycles=%%0d",cycles);' % (case['name'], len(case['expected']))]
        case_meta.append({'name': case['name'], 'expected_values': len(case['expected']),
                          'expected_sha256': hashlib.sha256(expected_path.read_bytes()).hexdigest(),
                          'register_writes': case['registers'], 'memory_input_sha256': hashlib.sha256(mem_path.read_bytes()).hexdigest()})
    top += ['if(read_beats==0 || write_beats==0) $fatal(1,"DMA not exercised");',
            '$display("RTL_FUNCTIONAL_PASS kernel=%s checks=%%0d read_beats=%%0d write_beats=%%0d cycles=%%0d",checks,read_beats,write_beats,cycles);' % kernel,
            '$finish;', 'end', 'endmodule']
    (output / 'tb.sv').write_text('\n'.join(top) + '\n')
    files = sorted((ip / 'hdl/verilog').glob('*.v'))
    if not files:
        raise ValueError('No exported Verilog files: ' + str(ip))
    (output / 'project.prj').write_text(''.join('verilog xil_defaultlib "%s"\n' % p.as_posix() for p in files)
                                        + 'sv xil_defaultlib "tb.sv"\n')
    return {'kernel': kernel, 'component_xml': str(ip / 'component.xml'), 'cases': case_meta,
            'rtl_sources': {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'scope': 'top RTL AXI-Lite CTRL + all DMA buses with independent integer Q10 reference',
            'limitations': ['one outstanding burst per memory port', 'no randomized stalls',
                            'bounded deterministic vectors, not whole-model equivalence', 'no implementation timing or hardware board validation']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-log', type=Path, help='Return nonzero unless a complete functional pass marker is present')
    parser.add_argument('--extended', action='store_true', help='Also exercise PW4-to-1280 and DW960 bias rows')
    parser.add_argument('--ip', action='append', metavar='KERNEL=IP_DIRECTORY')
    parser.add_argument('--vivado-bin', type=Path)
    parser.add_argument('--output', type=Path, help='Fresh external directory')
    args = parser.parse_args()
    if args.check_log:
        text = args.check_log.read_text(encoding='utf-8', errors='replace')
        passed = 'RTL_FUNCTIONAL_PASS' in text and 'MISMATCH ' not in text and 'Fatal:' not in text
        print('PASS' if passed else 'FAIL', args.check_log)
        return 0 if passed else 1
    if not args.ip or not args.vivado_bin or not args.output:
        parser.error('Provide --ip, --vivado-bin and --output, or --check-log')
    output = args.output.resolve()
    source_root = Path(__file__).resolve().parents[1]
    if output.exists() or output == source_root or source_root in output.parents:
        parser.error('Use a fresh output outside the submission tree')
    output.mkdir(parents=True)
    summary = []
    env = os.environ.copy()
    env.pop('PYTHONHOME', None); env.pop('PYTHONPATH', None)
    env['XILINX_LOCAL_USER_DATA'] = 'no'
    for item in args.ip:
        kernel, directory = item.split('=', 1)
        run = output / kernel; run.mkdir()
        result = generate(kernel, Path(directory).resolve(), run, args.extended)
        result.update(status='running', started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
        (run / 'result.json').write_text(json.dumps(result, indent=2))
        commands = [('xvlog', ['--prj', 'project.prj']),
                    ('xelab', ['xil_defaultlib.tb', '-L', 'unisims_ver', '-L', 'unimacro_ver', '-L', 'secureip', '-mt', 'off', '-s', 'tb_run']),
                    ('xsim', ['tb_run', '--runall'])]
        with (run / 'validation.log').open('w', encoding='utf-8') as log:
            for tool, parameters in commands:
                executable = args.vivado_bin / (tool + ('.bat' if os.name == 'nt' else ''))
                command = (['cmd.exe', '/d', '/c', str(executable)] if os.name == 'nt' else [str(executable)]) + parameters
                log.write('COMMAND ' + repr(command) + '\n'); log.flush()
                process = subprocess.run(command, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
                if process.returncode:
                    result.update(status='failed', failed_tool=tool, exit_code=process.returncode)
                    break
            else:
                result.update(status='pass', exit_code=0)
        text = (run / 'validation.log').read_text(encoding='utf-8', errors='replace')
        if result['status'] == 'pass' and ('RTL_FUNCTIONAL_PASS' not in text or 'MISMATCH ' in text or 'Fatal:' in text):
            result.update(status='failed', reason='Simulator exited without functional pass marker')
        result['markers'] = [line for line in text.splitlines() if line.startswith(('CASE_PASS ', 'RTL_FUNCTIONAL_PASS ', 'MISMATCH '))]
        result['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        (run / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        summary.append(result)
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(kernel, result['status'], run / 'validation.log', flush=True)
    return 0 if all(r['status'] == 'pass' for r in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
