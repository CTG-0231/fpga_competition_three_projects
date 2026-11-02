"""Package the new software with the unchanged bitstream from its source XSA."""
from pathlib import Path
import os
import sys
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT = Path(os.environ["FPGA_VITIS_WORK"]).resolve()
VITIS_ROOT = Path(os.environ["FPGA_VITIS_INSTALL"]).resolve()
OUT = ROOT / "artifacts"
OUT.mkdir(exist_ok=True)
subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', str(Path(__file__).with_name("verify_build.py"))], check=True)
files = {
    "trash_app.elf": ROOT / "workspace/trash_app/build/trash_app.elf",
    "trash_app.map": ROOT / "workspace/trash_app/build/trash_app.map",
    "fsbl.elf": ROOT / "workspace/trash_platform/export/trash_platform/sw/boot/fsbl.elf",
    "verification.json": ROOT / "verification.json",
}
for name, path in files.items():
    shutil.copy2(path, OUT / name)
xsa = ROOT / "hardware/design_1_wrapper_3.3v.xsa"
with zipfile.ZipFile(xsa) as archive:
    bit_names = [name for name in archive.namelist() if name.endswith(".bit")]
    assert len(bit_names) == 1
    bit_data = archive.read(bit_names[0])
    (OUT / "pl.bit").write_bytes(bit_data)
bif = OUT / "boot.bif"
bif.write_text("the_ROM_image:\n{\n  [bootloader] fsbl.elf\n  pl.bit\n  trash_app.elf\n}\n", encoding="ascii")
bootgen = str(VITIS_ROOT / "bin/bootgen.bat")
result = subprocess.run([bootgen, "-arch", "zynq", "-image", str(bif), "-o", "boot.bin", "-w", "on"], cwd=OUT,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(OUT / "bootgen.log").write_text(result.stdout, encoding="utf-8")
print(result.stdout)
if result.returncode or not (OUT / "boot.bin").exists() or "ERROR" in result.stdout:
    raise RuntimeError("Bootgen failed")
manifest = {
    "software_tool_version": "Vitis 2025.2",
    "hardware_origin": "Selected XSA, checked against software register definitions; see verification.json",
    "source_xsa_sha256": hashlib.sha256(xsa.read_bytes()).hexdigest(),
    "hardware_tested": False,
    "files": {name: {"bytes": (OUT / name).stat().st_size, "sha256": hashlib.sha256((OUT / name).read_bytes()).hexdigest()}
              for name in ["fsbl.elf", "pl.bit", "trash_app.elf", "boot.bin"]},
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("BOOT_PACKAGE_CREATED", OUT)
