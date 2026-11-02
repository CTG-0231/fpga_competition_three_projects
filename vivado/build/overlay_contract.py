"""Validate the exported pair before handing it to PYNQ."""
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

EXPECTED_REGISTERS = {
    'conv_0': {'IN1_V': 0x10, 'IN2_V': 0x18, 'IN3_V': 0x20,
               'WEIGHT_V': 0x28, 'BIAS_V': 0x30, 'OUT_V': 0x38},
    'fc_0': {'IN_V': 0x10, 'WEIGHT_V': 0x18, 'BIAS_V': 0x20, 'OUT_V': 0x28},
    'pwdwconv_0': {'PBUS1_V': 0x10, 'PBUS2_V': 0x18, 'PBUS3_V': 0x20,
                  'PBUS4_V': 0x28, 'SBUS1_V': 0x30, 'SBUS2_V': 0x38,
                  'CH_IN': 0x40, 'CH_OUT': 0x48, 'STRIDE': 0x50,
                  'FSIZE': 0x58, 'ACT': 0x60, 'MODE': 0x68},
    'shortcut_0': {'SRC1_V': 0x10, 'SRC2_V': 0x18, 'DEST_V': 0x20, 'LENGTH_R': 0x28},
}

# Only aliases cross-checked against the actual 2025.2 component.xml exports.
REGISTER_ALIASES = {
    'conv_0': {'BIAS': 'BIAS_V'},
    'shortcut_0': {'SRC1': 'SRC1_V', 'SRC2': 'SRC2_V', 'DEST': 'DEST_V'},
    'pwdwconv_0': {'SBUS1_R': 'SBUS1_V'},
    'fc_0': {'BIAS': 'BIAS_V'},
}
CONTROL_REGISTERS = {'CTRL': 0x00, 'GIER': 0x04, 'IP_IER': 0x08, 'IP_ISR': 0x0C}


def canonicalize_registers(instance, fields):
    """Validate reviewed register aliases/offsets without importing PYNQ.

    Callers must first check register width. Return the unchanged legacy
    contract names; reject unknown names, duplicate aliases and missing fields.
    """
    if instance not in EXPECTED_REGISTERS or not isinstance(fields, dict):
        raise ValueError('Unknown HLS register contract: ' + str(instance))
    expected = EXPECTED_REGISTERS[instance]
    aliases = REGISTER_ALIASES.get(instance, {})
    result = {}
    for raw, offset in fields.items():
        if not isinstance(raw, str) or type(offset) is not int:
            raise ValueError('Invalid register name/offset: ' + instance)
        key = aliases.get(raw.upper(), raw.upper())
        if key not in expected:
            raise ValueError('Unknown HLS register: ' + instance + '/' + raw)
        if key in result:
            raise ValueError('Conflicting register aliases: ' + instance + '/' + key)
        result[key] = offset
    if result != expected:
        raise ValueError('HLS register contract mismatch: ' + instance)
    return result


def inspect_overlay(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['part'] != 'xc7z020clg484-2':
        raise ValueError('Expected AC820 xc7z020clg484-2')
    if set(manifest['registers']) != set(EXPECTED_REGISTERS):
        raise ValueError('Driver register contract differs from XSA manifest')
    for name, fields in manifest['registers'].items():
        canonicalize_registers(name, fields)
    for name in ('leaf.bit', 'leaf.hwh'):
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != manifest['files'][name]:
            raise ValueError('Overlay checksum mismatch: ' + name)
    hwh = ET.parse(str(directory / 'leaf.hwh')).getroot()
    for name, expected in EXPECTED_REGISTERS.items():
        module = hwh.find(".//MODULE[@INSTANCE='{}']".format(name))
        if module is None:
            raise ValueError('Missing HLS module: ' + name)
        actual = {}
        controls = {}
        for register in module.findall('.//REGISTER'):
            key = register.get('NAME').upper()
            props = {p.get('NAME'):p.get('VALUE') for p in register.findall('PROPERTY')}
            if int(props['SIZE'],0) != 32:
                raise ValueError('HLS register width changed: ' + name + '/' + key)
            destination = controls if key in CONTROL_REGISTERS else actual
            if key in destination:
                raise ValueError('Duplicate HWH register: ' + name + '/' + key)
            destination[key] = int(props['ADDRESS_OFFSET'],0)
        canonicalize_registers(name, actual)
        if controls != CONTROL_REGISTERS:
            raise ValueError('HWH control register contract mismatch: ' + name)
    ranges = {m.get('INSTANCE'): int(m.get('BASEVALUE'), 0)
              for m in hwh.findall('.//MEMRANGE') if m.get('MEMTYPE') == 'REGISTER'}
    expected_addresses = {'conv_0': 0x43c00000, 'fc_0': 0x43c10000,
                          'pwdwconv_0': 0x43c20000, 'shortcut_0': 0x43c30000,
                          'axi_vdma_0': 0x43000000, 'v_tc_0': 0x43c40000}
    for name, address in expected_addresses.items():
        if ranges.get(name) != address:
            raise ValueError('HWH address contract mismatch: ' + name)
    return manifest


def load_overlay(directory, board, io_voltage):
    """Caller explicitly selects the physical board and bank-voltage variant."""
    directory = Path(directory)
    manifest = inspect_overlay(directory)
    if board != 'ac820':
        raise ValueError('This bitstream is for AC820, not PYNQ-Z1/Z2 pinouts')
    if io_voltage not in ('3.3','1.8') or manifest.get('io_voltage') != io_voltage:
        raise ValueError('Select the overlay matching the actual board I/O bank voltage')
    from pynq import Overlay
    overlay = Overlay(str(directory / 'leaf.bit'))
    for name in EXPECTED_REGISTERS:
        if name not in overlay.ip_dict:
            raise RuntimeError('PYNQ did not recognize required IP ' + name)
    return overlay
