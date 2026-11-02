"""Run with: D:/software/vivado2025.2/2025.2/Vitis/bin/vitis.bat -s create_platform.py"""
from pathlib import Path
import os
import sys
import json
import shutil
import hashlib
import re
import subprocess
import vitis

ROOT = Path(os.environ["FPGA_VITIS_WORK"]).resolve()
VITIS_ROOT = Path(os.environ["FPGA_VITIS_INSTALL"]).resolve()
WORKSPACE = ROOT / "workspace"
HW = ROOT / "hardware" / "design_1_wrapper_3.3v.xsa"
SOURCE_HW = Path(os.environ["FPGA_HW_XSA"]).resolve()
HW.parent.mkdir(parents=True, exist_ok=True)
if not HW.exists():
    shutil.copy2(SOURCE_HW, HW)
assert hashlib.sha256(HW.read_bytes()).digest() == hashlib.sha256(SOURCE_HW.read_bytes()).digest()

client = vitis.create_client()
try:
    client.set_workspace(str(WORKSPACE))
    if (WORKSPACE / "trash_platform" / "vitis-comp.json").exists():
        platform = client.get_component(name="trash_platform")
    else:
        platform = client.create_platform_component(
            name="trash_platform", hw_design=str(HW),
            os="standalone", cpu="ps7_cortexa9_0",
            domain_name="standalone_domain", generate_dtb=False,
        )
    domain = platform.get_domain(name="standalone_domain")
    if "xilffs" not in str(domain.get_libs()):
        domain.set_lib(lib_name="xilffs")
    # Cleaning removes CMakeCache, so apply the requested settings afterwards.
    # Regeneration alone preserves bsp.yaml values but can recreate default
    # CMake library options; neither operation is sufficient by itself.
    print("Regenerating and cleaning the platform/BSP", flush=True)
    domain.regenerate()
    platform.clean()
    bsp = WORKSPACE / "trash_platform/ps7_cortexa9_0/standalone_domain/bsp"
    generated = bsp / "libsrc/build_configs/gen_bsp"
    cmake = VITIS_ROOT / "tps/win64/cmake-3.24.2/bin/cmake.exe"
    ninja = VITIS_ROOT / "tps/mingw/10.0.0/win64.o/nt/bin/ninja.exe"
    configure = [str(cmake), "-G", "Ninja", "-S", bsp.as_posix(),
                 "-B", generated.as_posix(), "-DSUBDIR_LIST=ALL",
                 "-DCMAKE_MAKE_PROGRAM:FILEPATH=" + ninja.as_posix(),
                 "-DCMAKE_MODULE_PATH:PATH=" + bsp.as_posix(),
                 "-DCMAKE_TOOLCHAIN_FILE:FILEPATH=" + (bsp / "cortexa9_toolchain.cmake").as_posix(),
                 "-DCMAKE_SPECS_FILE:FILEPATH=" + (bsp / "Xilinx.spec").as_posix(),
                 "-DCMAKE_INCLUDE_PATH:PATH=" + (bsp / "include").as_posix(),
                 "-DCMAKE_LIBRARY_PATH:PATH=" + (bsp / "lib").as_posix()]
    # config_bsp does not select a generator. Prime the clean cache explicitly
    # so it does not default to unavailable NMake on Windows.
    subprocess.run(configure, check=True)
    domain.set_config(option="os", param="standalone_stdout", value="ps7_uart_1")
    domain.set_config(option="os", param="standalone_stdin", value="ps7_uart_1")
    domain.set_config(option="lib", param="XILFFS_use_lfn", value="1", lib_name="xilffs")
    domain.set_config(option="lib", param="XILFFS_fs_interface", value="1", lib_name="xilffs")
    domain.set_config(option="lib", param="XILFFS_read_only", value="false", lib_name="xilffs")
    print("PLATFORM_CONFIGURATION_CREATED", flush=True)
    # The Windows 2025.2 config_bsp helper caches backslashes in install paths.
    # CMake later parses \U in those paths as an invalid escape and can leave
    # stale published headers. Reconfigure through the bundled CMake with
    # normalized paths, retaining the API-set library options, then build the
    # actual archives and let platform.build publish headers and libraries.
    subprocess.run(configure, check=True)
    print("Building platform/BSP/FSBL", flush=True)
    result = platform.build()
    if result is False or "FAIL" in str(result).upper():
        raise RuntimeError("Vitis platform build returned failure")
    if not (WORKSPACE / "trash_platform/export/trash_platform/sw/boot/fsbl.elf").exists():
        raise RuntimeError("Vitis did not generate the new FSBL")
    exported = WORKSPACE / "trash_platform/export/trash_platform/sw/standalone_domain"
    config_headers = [generated / "include/xilffs_config.h",
                      bsp / "include/xilffs_config.h",
                      exported / "include/xilffs_config.h"]
    for header in config_headers:
        if not re.search(r"(?m)^#define\s+FILE_SYSTEM_USE_LFN\s+1\s*$",
                         header.read_text(encoding="utf-8")):
            raise RuntimeError(f"Published BSP does not enable long file names: {header}")
    header_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in config_headers}
    if len(header_hashes) != 1:
        raise RuntimeError("Generated, installed and exported xilffs headers differ")
    libraries = [generated / "libsrc/xilffs/src/libxilffs.a",
                 bsp / "lib/libxilffs.a", exported / "lib/libxilffs.a"]
    library_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries}
    if len(library_hashes) != 1:
        raise RuntimeError("Compiled, installed and exported xilffs archives differ")
    print("BSP_LFN_VERIFIED headers=3 libraries=3 FILE_SYSTEM_USE_LFN=1", flush=True)
    print("PLATFORM_BUILD_COMPLETED", flush=True)
finally:
    vitis.dispose()
