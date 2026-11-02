"""Create/sync/build the migrated application using the installed Vitis Python API."""
from pathlib import Path
import os
import sys
import shutil
import vitis

ROOT = Path(os.environ["FPGA_VITIS_WORK"]).resolve()
VITIS_ROOT = Path(os.environ["FPGA_VITIS_INSTALL"]).resolve()
WORKSPACE = ROOT / "workspace"
APP = WORKSPACE / "trash_app"
client = vitis.create_client()
try:
    client.set_workspace(str(WORKSPACE))
    if (APP / "vitis-comp.json").exists():
        app = client.get_component(name="trash_app")
    else:
        xpfm = WORKSPACE / "trash_platform/export/trash_platform/trash_platform.xpfm"
        app = client.create_app_component(
            name="trash_app", platform=str(xpfm), domain="standalone_domain",
            template="empty_application",
        )
    dest = APP / "src"
    for folder in ("src", "lib", "drivers"):
        shutil.copytree(ROOT / "app_src" / folder, dest / folder, dirs_exist_ok=True)
    cmake = dest / "CMakeLists.txt"
    s = cmake.read_text(encoding="utf-8")
    s = s.replace("aux_source_directory(${CMAKE_CURRENT_SOURCE_DIR} current_dir_sources)",
        'file(GLOB_RECURSE current_dir_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/*.c" "${CMAKE_CURRENT_SOURCE_DIR}/*.S")')
    if "# Migration verification flags" not in s:
        s += '''
# Migration verification flags
if(TARGET ${APP_NAME}.elf)
  target_compile_options(${APP_NAME}.elf PRIVATE -Werror=implicit-function-declaration -Werror=incompatible-pointer-types)
  target_link_options(${APP_NAME}.elf PRIVATE "-Wl,-Map=trash_app.map" "-Wl,--build-id=none")
endif()
'''
    cmake.write_text(s, encoding="utf-8")
    include_dirs = sorted({p.parent.as_posix() for p in dest.rglob("*.h")})
    app.set_app_config(key="USER_INCLUDE_DIRECTORIES", values=include_dirs)
    app.set_app_config(key="USER_LINK_LIBRARIES", values=["m"])
    app.set_app_config(key="USER_LINKER_SCRIPT", values=(dest / "src/lscript.ld").as_posix())
    print("APPLICATION_BUILD_STARTED", flush=True)
    result = app.build()
    if result is False or "FAIL" in str(result).upper():
        raise RuntimeError("Vitis application build returned failure")
    elf = APP / "build" / "trash_app.elf"
    if not elf.exists():
        raise RuntimeError("Vitis did not generate trash_app.elf")
    print("APPLICATION_BUILD_COMPLETED", flush=True)
finally:
    vitis.dispose()
