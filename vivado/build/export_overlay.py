"""Repackage an existing XSA as a PYNQ overlay; does not synthesize hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overlay_contract import (CONTROL_REGISTERS, canonicalize_registers)

HLS_POLICIES = ('reuse_original_unchanged_per_user_instruction',
                'regenerated_2025_2_original_algorithm')

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def bit_part(data):
    """Read the part field from the Xilinx .bit header."""
    cursor = 2 + struct.unpack('>H', data[:2])[0]
    marker_size = struct.unpack('>H', data[cursor:cursor + 2])[0]
    cursor += 2
    if marker_size != 1:
        raise ValueError('Unrecognized bitstream header')
    while cursor < len(data):
        key = data[cursor:cursor + 1]
        cursor += 1
        if key == b'e':
            break
        length = struct.unpack('>H', data[cursor:cursor + 2])[0]
        cursor += 2
        value = data[cursor:cursor + length]
        cursor += length
        if key == b'b':
            return value.rstrip(b'\0').decode('ascii')
    raise ValueError('Bitstream part field missing')


def export(xsa, output, io_voltage=None,
           hls_policy='reuse_original_unchanged_per_user_instruction'):
    xsa, output = Path(xsa), Path(output)
    if hls_policy not in HLS_POLICIES:
        raise ValueError('Select an explicit supported HLS provenance policy')
    with ZipFile(xsa) as archive:
        bits = [n for n in archive.namelist() if n.endswith('.bit')]
        hwhs = [n for n in archive.namelist() if n.endswith('.hwh')]
        if len(bits) != 1 or len(hwhs) != 1:
            raise ValueError('Require exactly one .bit and one .hwh in XSA')
        bit, hwh = archive.read(bits[0]), archive.read(hwhs[0])
        if io_voltage is None:
            io_voltage = {'design_1_wrapper_3.3v.xsa':'3.3',
                          'design_1_wrapper_1.8v.xsa':'1.8'}.get(xsa.name)
        if io_voltage not in ('3.3','1.8'):
            raise ValueError('Pass --io-voltage matching the actual rebuilt I/O constraints')
        root = ET.fromstring(hwh)
        system = ET.fromstring(archive.read('sysdef.xml')).find('SYSTEMINFO')
        part = system.get('PART')
        if part != 'xc7z020clg484-2' or bit_part(bit) != '7z020clg484':
            raise ValueError('This port supports the supplied AC820 xc7z020clg484-2 only')
        modules = {}
        for module in root.findall('.//MODULE'):
            params = {p.get('NAME'): p.get('VALUE')
                      for p in module.findall('./PARAMETERS/PARAMETER')}
            modules[module.get('INSTANCE')] = {
                'vlnv': module.get('VLNV'), 'parameters': params}
        registers = {}
        registers_raw = {}
        register_sources = {}
        for name in ['conv', 'fc', 'pwdwconv', 'shortcut']:
            module = root.find(".//MODULE[@INSTANCE='{}_0']".format(name))
            if module is None:
                raise ValueError('Missing HLS module in HWH: ' + name)
            fields = {}
            raw_fields = {}
            controls = {}
            for register in module.findall('.//REGISTER'):
                raw_name = register.get('NAME')
                key = raw_name.upper()
                properties = {p.get('NAME'):p.get('VALUE') for p in register.findall('PROPERTY')}
                if int(properties['SIZE'],0) != 32:
                    raise ValueError('This host driver expects 32-bit HLS registers')
                offset = int(properties['ADDRESS_OFFSET'],0)
                if key in fields or key in controls:
                    raise ValueError('Duplicate HWH register name: ' + raw_name)
                if key in CONTROL_REGISTERS:
                    controls[key] = offset
                else:
                    fields[key] = offset
                    raw_fields[raw_name] = offset
            canonicalize_registers(name + '_0', fields)
            if controls != CONTROL_REGISTERS:
                raise ValueError('HWH control register contract mismatch: ' + name)
            registers[name + '_0'] = fields
            registers_raw[name + '_0'] = raw_fields
            register_sources[name + '_0'] = 'HWH registers'
            headers = [n for n in archive.namelist() if re.search(
                r'(?:^|/)drivers/' + name + r'_v[^/]+/src/x' + name + r'_hw\.h$', n)]
            for header in headers:
                source = archive.read(header).decode()
                generated = {key: int(value,16) for key,value in re.findall(
                    r'#define\s+X\w+_CTRL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)',source)}
                if generated != fields:
                    raise ValueError('HWH disagrees with generated header: ' + header)
                register_sources[name + '_0'] = 'HWH cross-checked against ' + header
        manifest = {
            'schema': 1, 'source_xsa': xsa.name,
            'source_xsa_sha256': sha256(xsa.read_bytes()), 'part': part,
            'vivado_version': root.get('VIVADOVERSION'),
            'io_voltage': io_voltage,
            'hls_policy': hls_policy,
            'bit_part': bit_part(bit),
            'files': {'leaf.bit': sha256(bit), 'leaf.hwh': sha256(hwh)},
            'registers': registers,
            'registers_raw': registers_raw,
            'register_sources': register_sources,
            'modules': {k: v for k, v in modules.items() if k in
                        ['conv_0', 'fc_0', 'pwdwconv_0', 'shortcut_0',
                         'axi_vdma_0', 'v_tc_0', 'processing_system7_0']},
            'validation': 'exported_pair_only_not_board_tested',
        }
        output.mkdir(parents=True, exist_ok=True)
        for name, content in [('leaf.bit', bit), ('leaf.hwh', hwh)]:
            (output / name).write_bytes(content)
        (output / 'manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        # Reference BD Tcl alone is not a standalone reproducible build.
        if 'design_1_bd.tcl' in archive.namelist():
            (output / 'design_1_reference.tcl').write_bytes(archive.read('design_1_bd.tcl'))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xsa', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--io-voltage', choices=['3.3','1.8'])
    parser.add_argument('--hls-policy', choices=HLS_POLICIES,
                        default=HLS_POLICIES[0], help='Record the actual HLS RTL provenance')
    args = parser.parse_args()
    result = export(args.xsa, args.output, args.io_voltage, args.hls_policy)
    print(json.dumps({k: result[k] for k in ['source_xsa', 'part', 'validation']}, indent=2))
