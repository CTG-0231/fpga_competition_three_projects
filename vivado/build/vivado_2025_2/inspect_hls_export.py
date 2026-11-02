"""Compare native HLS IP register/interface contracts before integrating a new export.

No Vivado/Vitis invocation. Input files are read only; the report records every
register difference rather than declaring a newer compiler ABI equivalent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def component(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    namespace = root.tag.split('}')[0].lstrip('{')
    ns = {'s': namespace}
    def text(node, name):
        return node.findtext('s:' + name, namespaces=ns)
    def num(value):
        if value is None:
            return None
        return int(value, 16 if value.lower().startswith('0x') else 10)
    identity = ':'.join(text(root, name) or '' for name in ('vendor', 'library', 'name', 'version'))
    maps = []
    for memory in root.findall('s:memoryMaps/s:memoryMap', ns):
        blocks = []
        for block in memory.findall('s:addressBlock', ns):
            registers = []
            for reg in block.findall('s:register', ns):
                fields = []
                for field in reg.findall('s:field', ns):
                    fields.append({'name': text(field, 'name'), 'offset': num(text(field, 'bitOffset')),
                        'width': num(text(field, 'bitWidth')), 'access': text(field, 'access'),
                        'read_action': text(field, 'readAction'), 'modified_write_value': text(field, 'modifiedWriteValue')})
                registers.append({'name': text(reg, 'name'), 'offset': num(text(reg, 'addressOffset')),
                    'size': num(text(reg, 'size')), 'access': text(reg, 'access'),
                    'reset': reg.findtext('s:reset/s:value', namespaces=ns), 'fields': fields})
            blocks.append({'name': text(block, 'name'), 'base': num(text(block, 'baseAddress')),
                           'range': num(text(block, 'range')), 'width': num(text(block, 'width')), 'registers': registers})
        maps.append({'name': text(memory, 'name'), 'blocks': blocks})
    interfaces = []
    for interface in root.findall('s:busInterfaces/s:busInterface', ns):
        bus = interface.find('s:busType', ns)
        pins = {}
        for pin in interface.findall('s:portMaps/s:portMap', ns):
            pins[pin.findtext('s:logicalPort/s:name', namespaces=ns)] = pin.findtext('s:physicalPort/s:name', namespaces=ns)
        interfaces.append({'name': text(interface, 'name'),
                           'bus_type': {k.split('}')[-1]: v for k, v in bus.attrib.items()} if bus is not None else None,
                           'port_maps': pins})
    ports = {}
    for port in root.findall('s:model/s:ports/s:port', ns):
        ports[text(port, 'name')] = {
            'direction': port.findtext('s:wire/s:direction', namespaces=ns),
            'left': port.findtext('s:wire/s:vector/s:left', namespaces=ns),
            'right': port.findtext('s:wire/s:vector/s:right', namespaces=ns)}
    return {'component': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'vlnv': identity,
            'memory_maps': maps, 'interfaces': interfaces, 'ports': ports}


def differences(before, after, path=''):
    result = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            result += differences(before.get(key), after.get(key), path + '/' + str(key))
    elif isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            result += differences(old, new, path + '/' + str(index))
    elif before != after:
        result.append({'path': path, 'before': before, 'after': after})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_component', type=Path)
    p.add_argument('new_component', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    old, new = component(args.original_component), component(args.new_component)
    diffs = differences(old['memory_maps'], new['memory_maps'], '/memory_maps')
    if old['vlnv'] != new['vlnv']:
        diffs.append({'path': '/vlnv', 'before': old['vlnv'], 'after': new['vlnv']})
    iface_diffs = differences(old['interfaces'], new['interfaces'], '/interfaces')
    port_diffs = differences(old['ports'], new['ports'], '/ports')
    report = {'status': 'IDENTICAL_RECORDED_CONTRACT' if not diffs and not iface_diffs and not port_diffs else 'REVIEW_REQUIRED',
              'original': old, 'new': new, 'register_differences': diffs, 'interface_differences': iface_diffs,
              'port_differences': port_diffs,
              'scope': 'XML register names, offsets, sizes, access/reset/field semantics and interface pin maps; not arithmetic equivalence, RTL timing, physical signals or board testing'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'register_differences': len(diffs), 'interface_differences': len(iface_diffs), 'port_differences': len(port_diffs)}))
    return 0 if report['status'] == 'IDENTICAL_RECORDED_CONTRACT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
