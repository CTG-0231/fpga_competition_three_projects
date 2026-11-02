"""Fail closed unless these generated HLS AXI adapters match the reviewed ID=0 profile.

This is a narrow source-pattern check, not a Verilog equivalence checker. The
separate top-level RTL test must also assert AWID/ARID/WID==0 and check results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


MASTERS = {
    'conv': ('IN1', 'IN2', 'IN3', 'W', 'OUT_r'),
    'fc': ('IN_r', 'W', 'O'),
    'pwdwconv': ('PBUS1', 'PBUS2', 'PBUS3', 'PBUS4', 'SBUS1', 'SBUS2'),
    'shortcut': ('IN1', 'IN2', 'OUT_r'),
}


def zero(value):
    return bool(re.fullmatch(r"(?:\d+)?'[bBdDhH]0+|0", value.strip()))


def review(ip_root=None, folders=None):
    records, failures = [], []
    for core, masters in MASTERS.items():
        folder = Path(folders[core]) if folders is not None else Path(ip_root) / core
        component = ET.parse(folder / 'component.xml').getroot()
        ns = {'s': component.tag.split('}')[0].lstrip('{')}
        params = {p.findtext('s:name', namespaces=ns): p.findtext('s:value', namespaces=ns)
                  for p in component.findall('s:parameters/s:parameter', ns)}
        actual = {p.name for p in (folder / 'hdl/verilog').glob('*_m_axi.v')}
        expected = {master + '_m_axi.v' for master in masters}
        if actual != expected:
            failures.append(core + ': adapter set differs from reviewed 17-master profile')
        for master in masters:
            name = 'C_M_AXI_' + master.upper()
            if params.get(name + '_ID_WIDTH') != '1':
                failures.append(core + '/' + master + ': ID width is not 1')
            if params.get(name + '_ENABLE_ID_PORTS') != 'true':
                failures.append(core + '/' + master + ': expected unedited package default true')
            source = folder / 'hdl/verilog' / (master + '_m_axi.v')
            text = source.read_text(encoding='utf-8')
            # Only the adapter module, before appended helper-module definitions.
            first_module = text.split('endmodule', 1)[0]
            counts = re.findall(r'\bNUM_(?:READ|WRITE)_PORTS\s*=\s*(\d+)', first_module)
            if len(counts) != 2 or any(int(value) not in (0, 1) for value in counts):
                failures.append(core + '/' + master + ': unsupported logical ID/channel count')
            functions = re.findall(r'\bfunction\b.*?\bendfunction', text, re.S)
            maps = []
            for func in functions:
                for kind in ('compress_axi_id', 'decompress_axi_id'):
                    values = re.findall(r'\b' + kind + r'\s*=\s*([^;]+);', func)
                    if values:
                        maps.append({'name': kind, 'values': values})
                        if not all(zero(value) for value in values):
                            failures.append(core + '/' + master + ': nonzero ID mapping')
            if not any(x['name'] == 'compress_axi_id' for x in maps) or not any(x['name'] == 'decompress_axi_id' for x in maps):
                failures.append(core + '/' + master + ': expected ID map functions not found')
            # Active local IDs and unused external IDs must be explicitly zero.
            direct = re.findall(r'\bassign\s+((?:local_AXI_)?(?:ARID|AWID)|WID)\s*=\s*([^;]+);', first_module)
            allowed = "{C_M_AXI_ID_WIDTH{1'b0}}"
            if not direct or any(re.sub(r'\s+', '', value) != allowed for _, value in direct):
                failures.append(core + '/' + master + ': unexpected direct ID expression')
            records.append({'core': core, 'master': master, 'file': str(source),
                            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                            'logical_ports': counts, 'maps': maps, 'direct_assignments': direct})
    return {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
            'masters': len(records), 'records': records,
            'scope': 'Reviewed 2025.2 generated adapter source patterns only. Not formal equivalence, arithmetic verification, physical timing or board validation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ip_root', type=Path, help='Four folders conv/fc/pwdwconv/shortcut')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = review(args.ip_root)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'failures': result['failures'], 'masters': result['masters']}))
    return result['status'] != 'PASS'


if __name__ == '__main__':
    raise SystemExit(main())
