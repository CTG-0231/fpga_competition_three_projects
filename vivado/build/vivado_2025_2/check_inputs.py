"""Pre-synthesis checks for this AC820 design with four actual 2025.2 HLS exports."""
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def within(path, root):
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def normalized(value):
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r'[+-]?\d+(?:\.\d+)?', value):
            return Decimal(value)
        if re.fullmatch(r'0[xX][0-9a-fA-F]+', value):
            return int(value, 16)
    return value


def effective_addresses(design):
    """Merge the 2019 and split 2025 address-space serialization strictly."""
    result, additions = {}, {}
    sources = [(owner, value) for owner, value in design.get('addressing', {}).items()]
    sources += [('/' + owner, value['addressing']) for owner, value in design['components'].items() if 'addressing' in value]
    for owner, value in sources:
        if set(value) != {'address_spaces'}:
            raise ValueError('Unknown address-owner schema: ' + owner)
        for name, space in value['address_spaces'].items():
            key = owner + '/' + name
            item = result.setdefault(key, {'segments': {}})
            for field, value in space.items():
                if field in ('range', 'width'):
                    if field in item and item[field] != value:
                        raise ValueError('Conflicting address-space value: ' + key + '/' + field)
                    item[field] = value
                elif field == 'segments':
                    for segment, definition in value.items():
                        base = {k: definition[k] for k in ('address_block', 'offset', 'range')}
                        if segment in item['segments'] and item['segments'][segment] != base:
                            raise ValueError('Conflicting address segment: ' + key + '/' + segment)
                        item['segments'][segment] = base
                        extra = {k: v for k, v in definition.items() if k not in base}
                        if extra:
                            additions[key + '/segments/' + segment] = extra
                elif field == 'local_memory_map':
                    additions[key + '/local_memory_map'] = value
                else:
                    raise ValueError('Unknown address-space field: ' + key + '/' + field)
    return result, additions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('native_project', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    workspace = output / 'workspace'
    bd_root = workspace / 'inputs/bd'
    manifest = json.loads((workspace / 'prepare_manifest.json').read_text())
    failures, checks, details = [], [], {}
    instance_overrides = []
    id_wrapper_checks = []
    id_spec = importlib.util.spec_from_file_location('_single_id_generated_gate', Path(__file__).with_name('review_single_id.py'))
    id_module = importlib.util.module_from_spec(id_spec)
    id_spec.loader.exec_module(id_module)
    id_source_review = id_module.review(workspace / 'ip_repo')
    failures.extend(id_source_review['failures'])
    for rel, expected in manifest['files'].items():
        if rel == 'inputs/bd/design_1.bd':
            continue
        actual = digest(workspace / rel)
        checks.append({'file': rel, 'expected': expected, 'actual': actual})
        if actual != expected:
            failures.append('Staged source changed: ' + rel)
    xcis = list(bd_root.rglob('*.xci'))
    for path in xcis:
        ip = json.loads(path.read_text())['ip_inst']
        if not within(path.parent / ip['gen_directory'], output):
            failures.append('XCI generation directory escaped output: ' + str(path))
    xpr = output / 'p/leaf.xpr'
    project = ET.parse(xpr).getroot()
    project_sources = []
    for item in project.findall('.//File'):
        native = item.get('Path', '').replace('$PPRDIR', str(xpr.parent))
        path = Path(native).resolve()
        project_sources.append(str(path))
        if '$' in native or not within(path, workspace) or not path.is_file():
            failures.append('Project source is missing or escaped workspace: ' + native)
    expected_sources = {str((workspace / rel).resolve()) for rel in manifest['files']
                        if rel.startswith(('inputs/rtl/', 'inputs/constraints/'))}
    expected_sources.update(str((bd_root / rel).resolve()) for rel in ('design_1.bd', 'generated/hdl/design_1_wrapper.v'))
    if set(project_sources) != expected_sources:
        failures.append('Unexpected project source-file set')
    repo_paths = [Path(v.get('Val').replace('$PPRDIR', str(xpr.parent))).resolve()
                  for v in project.findall('.//Configuration/Option[@Name="IPRepoPath"]')]
    if set(repo_paths) != {(workspace / 'ip_repo' / core).resolve() for core in ('conv', 'fc', 'pwdwconv', 'shortcut')}:
        failures.append('Unexpected project IP repository paths')
    # This module uses only the standard library at import time, never PYNQ/MMIO.
    overlay_file = Path(__file__).resolve().parents[2] / 'build/overlay_contract.py'
    spec = importlib.util.spec_from_file_location('_ac820_contract_only', overlay_file)
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    hwh_file = bd_root / 'generated/hw_handoff/design_1.hwh'
    hwh = ET.parse(hwh_file).getroot()
    for core in ('conv', 'fc', 'pwdwconv', 'shortcut'):
        found = list(bd_root.glob('ip/design_1_' + core + '_*/design_1_*.xci'))
        if len(found) != 1:
            failures.append('Expected exactly one XCI for ' + core)
            continue
        ip = json.loads(found[0].read_text())['ip_inst']
        if ip['component_reference'] != 'xilinx.com:hls:' + core + ':0.0':
            failures.append('Unexpected custom IP identity: ' + core)
        reference_file = workspace / 'inputs/reference_hls_ports.json'
        old_ports = json.loads(reference_file.read_text())['cores'][core]['ports']
        if old_ports != ip['boundary']['ports']:
            failures.append('Physical HLS ports differ from native design: ' + core)
        component = ET.parse(workspace / 'ip_repo' / core / 'component.xml').getroot()
        namespace = component.tag.split('}')[0].lstrip('{')
        ns = {'s': namespace}
        # Disabled optional ID input pins must be physically tied to zero by
        # Vivado's generated wrapper; output IDs must remain unconnected.
        wrappers = list(bd_root.glob('generated/ip/design_1_' + core + '_*/synth/*.v'))
        wrapper_text = '\n'.join(path.read_text() for path in wrappers)
        for port in component.findall('s:model/s:ports/s:port', ns):
            name = port.findtext('s:name', namespaces=ns)
            match = re.fullmatch(r'm_axi_\w+_(AWID|ARID|WID|BID|RID)', name or '')
            if not match:
                continue
            bindings = re.findall(r'\.' + re.escape(name) + r'\s*\(\s*([^)]*)\)', wrapper_text)
            expected_zero = match.group(1) in ('BID', 'RID')
            okay = len(bindings) == 1 and (bool(re.fullmatch(r"1'[bBdDhH]0", bindings[0])) if expected_zero else bindings[0] == '')
            id_wrapper_checks.append({'core': core, 'port': name, 'binding': bindings,
                                      'expected': 'one_bit_zero' if expected_zero else 'unconnected_output', 'passed': okay})
            if not okay:
                failures.append('Unsafe disabled-ID wrapper binding: ' + core + '/' + name)
        param_comparisons = []
        for group, xpath in [('component_parameters', 's:parameters/s:parameter'),
                             ('model_parameters', 's:model/s:modelParameters/s:modelParameter')]:
            generated = {k: v[0]['value'] for k, v in ip['parameters'][group].items()}
            for item in component.findall(xpath, ns):
                name = item.findtext('s:name', namespaces=ns)
                expected = item.findtext('s:value', namespaces=ns)
                if name == 'Component_Name' or name.endswith(('_BASEADDR', '_HIGHADDR')):
                    continue
                if name not in generated:
                    continue
                actual = generated[name]
                param_comparisons.append({'group': group, 'name': name, 'expected': expected, 'actual': actual})
                if normalized(expected) != normalized(actual):
                    if (group == 'component_parameters' and re.fullmatch(r'C_M_AXI_\w+_ENABLE_ID_PORTS', name)
                            and expected == 'true' and actual == 'false'):
                        instance_overrides.append({'core': core, 'parameter': name, 'package': expected, 'instance': actual,
                            'reason': 'Reviewed official single-ID compatibility configuration; no package/RTL edit'})
                    else:
                        failures.append('HLS package parameter changed: ' + core + '/' + group + '/' + name)
                if re.fullmatch(r'C_M_AXI_\w+_ID_WIDTH', name) and normalized(actual) != 1:
                    failures.append('Expected reviewed one-bit ID width: ' + core + '/' + name)
        expected_regs = {}
        for register in component.findall('s:memoryMaps/s:memoryMap/s:addressBlock/s:register', ns):
            name = register.findtext('s:name', namespaces=ns)
            expected_regs[name.upper()] = (int(register.findtext('s:addressOffset', namespaces=ns), 0),
                                           int(register.findtext('s:size', namespaces=ns), 0))
        instance = core + '_0'
        module = hwh.find('.//MODULE[@INSTANCE="' + instance + '"]')
        actual_regs, data_regs, controls = {}, {}, {}
        if module is None:
            failures.append('HWH missing module: ' + instance)
            continue
        for register in module.findall('.//REGISTER'):
            name = register.get('NAME').upper()
            props = {x.get('NAME'): x.get('VALUE') for x in register.findall('PROPERTY')}
            offset, size = int(props['ADDRESS_OFFSET'], 0), int(props['SIZE'], 0)
            if name in actual_regs:
                failures.append('Duplicate register: ' + instance + '/' + name)
            actual_regs[name] = (offset, size)
            if size != 32:
                failures.append('Register no longer 32 bits: ' + instance + '/' + name)
            (controls if name in overlay.CONTROL_REGISTERS else data_regs)[name] = offset
        if actual_regs != expected_regs:
            failures.append('Generated HWH differs from new IP package register map: ' + instance)
        try:
            overlay.canonicalize_registers(instance, data_regs)
        except ValueError as exc:
            failures.append(str(exc))
        if controls != overlay.CONTROL_REGISTERS:
            failures.append('Control-register offsets changed: ' + instance)
        details[core] = {'xci': str(found[0]), 'registers': actual_regs,
                         'package_parameter_comparisons': param_comparisons}
    video_expected = {
        'v_vid_in_axi4s': {'component_parameters': {'C_VID_NATIVE_DE': '0', 'C_M_AXIS_VIDEO_FORMAT': '12', 'C_HAS_ASYNC_CLK': '1'},
                          'model_parameters': {'C_NATIVE_DATA_WIDTH': '8', 'C_M_AXIS_TDATA_WIDTH': '8'}},
        'axis_dwidth_converter': {'component_parameters': {'S_TDATA_NUM_BYTES': '1', 'M_TDATA_NUM_BYTES': '2'},
                                  'model_parameters': {'C_S_AXIS_TDATA_WIDTH': '8', 'C_M_AXIS_TDATA_WIDTH': '16'}},
        'axis_subset_converter': {'component_parameters': {'S_TDATA_NUM_BYTES': '2', 'M_TDATA_NUM_BYTES': '3',
                                  'TDATA_REMAP': "tdata[15:11],3'b000,tdata[10:5],2'b00,tdata[4:0],3'b000",
                                  'TKEEP_REMAP': "1'b1,tkeep[1:0]"},
                                 'model_parameters': {'C_S_AXIS_TDATA_WIDTH': '16', 'C_M_AXIS_TDATA_WIDTH': '24'}},
        'axi_vdma': {'component_parameters': {'c_m_axis_mm2s_tdata_width': '24', 'c_s_axis_s2mm_tdata_width': '24', 'c_addr_width': '32', 'c_num_fstores': '1'},
                     'model_parameters': {'C_M_AXIS_MM2S_TDATA_WIDTH': '24', 'C_S_AXIS_S2MM_TDATA_WIDTH': '24'}}}
    for core, groups in video_expected.items():
        path = next(bd_root.glob('ip/design_1_' + core + '_*/design_1_*.xci'))
        ip = json.loads(path.read_text())['ip_inst']
        for group, expected in groups.items():
            actual = {k: v[0]['value'] for k, v in ip['parameters'][group].items()}
            for key, value in expected.items():
                if normalized(actual.get(key)) != normalized(value):
                    failures.append('Video contract changed: ' + core + '/' + group + '/' + key)
    before, after = [(output / name).read_text() for name in ('address_before.tsv', 'address_after.tsv')]
    if before != after:
        failures.append('Address segment snapshot changed')
    original_bd_path = args.native_project / 'trash.srcs/sources_1/bd/design_1/design_1.bd'
    if digest(original_bd_path) != manifest['files']['inputs/bd/design_1.bd']:
        failures.append('Original BD reference changed after preparation')
    original_bd = json.loads(original_bd_path.read_text())['design']
    generated_bd = json.loads((bd_root / 'design_1.bd').read_text())['design']
    source_addresses, source_additions = effective_addresses(original_bd)
    generated_addresses, generated_additions = effective_addresses(generated_bd)
    if source_addresses != generated_addresses:
        failures.append('Original-to-generated effective address spaces/segments changed')
    shared = bd_root / 'ipshared'
    hls_sources = []
    for core in ('conv', 'fc', 'pwdwconv', 'shortcut'):
        tops = list(shared.glob('*/hdl/verilog/' + core + '.v'))
        if len(tops) != 1:
            failures.append('Expected one actual ipshared top for ' + core)
            continue
        group = tops[0].parents[2]
        for path in group.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in ('.v', '.vh', '.vhd', '.xdc'):
                continue
            rel = path.relative_to(group)
            expected = workspace / 'ip_repo' / core / rel
            same = expected.is_file() and digest(path) == digest(expected)
            hls_sources.append({'actual': str(path), 'source': str(expected), 'same': same,
                                'sha256': digest(path)})
            if not same:
                failures.append('Actual HLS source mismatch: ' + str(path))
    report = {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
              'hls_policy': manifest['logic_policy'], 'source_hashes': checks,
              'hls': details, 'instance_overrides': instance_overrides, 'id_wrapper_checks': id_wrapper_checks,
              'id_source_review': id_source_review,
              'actual_hls_sources': hls_sources, 'xci_count': len(xcis),
              'address_snapshots_equal': before == after,
              'effective_address_spaces_equal': source_addresses == generated_addresses,
              'project_source_paths': project_sources, 'project_ip_repo_paths': [str(p) for p in repo_paths],
              'effective_addresses': generated_addresses,
              'addressing_additional_fields': {'source': source_additions, 'generated': generated_additions,
                  'scope': 'Recorded derived address-binding/local-memory-map metadata. Effective offsets/ranges/widths/address blocks are compared independently; this is not a full BD semantic equivalence claim.'},
              'scope': 'Pre-synthesis source, physical-port, parameter/register, video, address and isolation checks. Not arithmetic equivalence, timing closure or board validation.'}
    (output / 'migration_input_gate.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'failures': failures,
                      'source_hashes': len(checks), 'actual_hls_sources': len(hls_sources)}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
