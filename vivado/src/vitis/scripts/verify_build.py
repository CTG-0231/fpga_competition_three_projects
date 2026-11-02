"""Verify the real ARM ELF, SDT BSP and migrated hardware bindings."""
from pathlib import Path
import os
import sys
import hashlib
import json
import re
import struct
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trash_pynq.overlay import canonicalize_registers

ROOT = Path(os.environ["FPGA_VITIS_WORK"]).resolve()
VITIS_ROOT = Path(os.environ["FPGA_VITIS_INSTALL"]).resolve()
ELF = ROOT / "workspace/trash_app/build/trash_app.elf"
PLATFORM = ROOT / "workspace/trash_platform/export/trash_platform"
INC = PLATFORM / "sw/standalone_domain/include"
TOOL_BIN = VITIS_ROOT / "gnu/aarch32/nt/gcc-arm-none-eabi/bin"

def tool(name, *args):
    return subprocess.check_output([str(TOOL_BIN / name), *map(str, args)], text=True)

data = ELF.read_bytes()
assert data[:7] == b"\x7fELF\x01\x01\x01", "Expected little-endian ELF32"
header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
assert header[2] == 40, "Expected ARM machine"
assert header[4] == 0x00100000, "Unexpected entry point"
phoff, phsize, phcount = header[5], header[9], header[10]
segments = []
for i in range(phcount):
    typ, off, va, pa, filesz, memsz, flags, align = struct.unpack_from("<IIIIIIII", data, phoff + i * phsize)
    if typ == 1:
        assert 0x00100000 <= pa < pa + memsz <= 0x12100000, "ELF overlaps video buffers or has an unexpected load address"
        segments.append({"address": hex(pa), "file_bytes": filesz, "memory_bytes": memsz})

symbols = {}
for line in tool("arm-none-eabi-nm.exe", "-n", ELF).splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = int(fields[0], 16)
assert symbols["_heap_end"] - symbols["_heap"] == 0x10000000
assert symbols["_stack"] - symbols["_stack_end"] == 0x200000
assert symbols["_end"] <= 0x12100000
for name in ["hls_conv", "hls_fc", "hls_pwdwconv", "hls_shortcut", "fatfs", "Intc"]:
    assert name in symbols

macros = {}
for name, value in re.findall(r"^#define\s+(\w+)\s+(0x[0-9a-fA-F]+|\d+)\s*$", (INC / "xparameters.h").read_text(), re.M):
    macros[name] = int(value, 0)
assert [macros[n] for n in ["XPAR_CONV_0_BASEADDR", "XPAR_FC_0_BASEADDR", "XPAR_PWDWCONV_0_BASEADDR", "XPAR_SHORTCUT_0_BASEADDR"]] == [0x43C00000, 0x43C10000, 0x43C20000, 0x43C30000]
assert macros["XPAR_AXI_VDMA_0_NUM_FSTORES"] == 1
interrupts = {label: (macros[macro] & 0xFFF) + 32 for label, macro in {
    "UART1": "XPAR_UART1_INTERRUPTS", "IIC0": "XPAR_XIICPS_0_INTERRUPTS",
    "IIC1": "XPAR_XIICPS_1_INTERRUPTS", "GPIO": "XPAR_XGPIOPS_0_INTERRUPTS",
}.items()}
assert interrupts == {"UART1": 82, "IIC0": 57, "IIC1": 80, "GPIO": 52}
ffs = (INC / "xilffs_config.h").read_text()
assert re.search(r"#define\s+FILE_SYSTEM_USE_LFN\s+1", ffs)
assert "#define FILE_SYSTEM_READ_ONLY" not in ffs
assert (PLATFORM / "sw/boot/fsbl.elf").is_file()

# The interface gate is produced from the selected XSA, not a stale BSP.
from xml.etree import ElementTree as ET
from zipfile import ZipFile
with ZipFile(ROOT / "hardware/design_1_wrapper_3.3v.xsa") as archive:
    hwhs = [n for n in archive.namelist() if n.endswith('.hwh')]
    assert len(hwhs) == 1
    hwh = ET.fromstring(archive.read(hwhs[0]))
for driver in ("conv", "fc", "pwdwconv", "shortcut"):
    module = hwh.find(".//MODULE[@INSTANCE='{}_0']".format(driver))
    assert module is not None, driver
    actual = {}
    for register in module.findall('.//REGISTER'):
        if register.get('NAME') in ('CTRL', 'GIER', 'IP_IER', 'IP_ISR'):
            continue
        props = {p.get('NAME'): p.get('VALUE') for p in register.findall('PROPERTY')}
        assert int(props['SIZE'], 0) == 32
        actual[register.get('NAME').upper()] = int(props['ADDRESS_OFFSET'], 0)
    header_text = (ROOT / f"app_src/drivers/{driver}/x{driver}_hw.h").read_text()
    expected = {key: int(value, 16) for key, value in re.findall(
        r'#define\s+X\w+_CTRL_ADDR_(\w+)_DATA\s+(0x[0-9a-fA-F]+)', header_text)}
    canonical = canonicalize_registers(driver + '_0', actual)
    assert canonical == expected, (driver, actual, expected)

report = {"result": "PASS", "toolchain": "Vitis 2025.2 / ARM GCC 13.3.0", "hardware_xsa": {"sha256": hashlib.sha256((ROOT / "hardware/design_1_wrapper_3.3v.xsa").read_bytes()).hexdigest(), "vivado_version": hwh.get("VIVADOVERSION")},
          "entry_point": hex(header[4]), "load_segments": segments,
          "heap_start": hex(symbols["_heap"]), "heap_end": hex(symbols["_heap_end"]),
          "application_end": hex(symbols["_end"]), "video_reserved_start": "0x12100000",
          "interrupt_ids": interrupts, "long_filenames": True, "elf_sha256": hashlib.sha256(data).hexdigest(),
          "hardware_tested": False}
(ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
