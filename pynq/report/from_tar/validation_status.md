# Validation status

Date: 2026-10-23, Asia/Shanghai.

| Check | Actual result | Evidence |
| --- | --- | --- |
| Host regression tests | 41 passed, 0 failed, 0 skipped | `host_tests.json`, `host_tests.log` |
| Original C preprocessing / float32-to-Q10 conversion | Compiled C expression references match | `sim/test_model.py`, test log |
| Real rice weights | 106 files loaded and converted; original bytes unchanged | `real_weights_check.json`, `../data/model_manifest.json` |
| Original HLS source preservation | All 12 files byte-identical | `hls_source_integrity.json` |
| Original FC / shortcut arithmetic | Three component cases match compiled original HLS source | `hls_component_reference.json` |
| Original bit/HWH pairing | Both variants checked; 3v3 equals original Vivado and active Vitis bit | `hardware_audit.md`, overlay manifests |
| Fresh hardware input preparation | 251 required source files copied and SHA256 checked | `../build/work/prepared/prepare_manifest.json` |
| LCD layout | Two 800x480 previews inspected; five UI tests passed | UI previews, host test log |
| Notebook | All cells parse as Python 3.8, no fabricated output cells; live handles preserved when initialization is repeated | `sim/test_workflow.py` |
| Actual vendor kernel / DTB | Embedded config includes I2C/GPIO/pinctrl; original I2C0/1 are disabled | `board_image_audit.md`, `board_image_fdt.json` |
| Boot DTB and FIT | Compiled/merged offline; only permitted peripheral properties change; new FIT retains kernel bytes and validates hashes | `boot_dtb_validation.json`, `../board/linux/boot_patch/manifest.json` |
| 2025.2 installation | Installer downloaded, signature Valid, client extracted; current command process has no administrator rights | `toolchain_2025_2.md` |
| Vivado 2025.2 implementation | Not executed | No new timing/resource/bitstream claims |
| SD image write / PYNQ board run | Not executed | Board not connected to this task |
| Full-network golden logits, dataset accuracy, CPU baseline | Not measured | Must use identical inputs and weights on the board |

Host tests use mock MMIO/device memory for hardware calls. The FC/shortcut component reference uses the already installed 2018.3 fixed-point headers and GCC; it neither upgrades nor downgrades the Vivado project. These checks do not establish full-network or board equivalence.

The fixed-input CLI now validates weights without CMA allocation, downloads the overlay, then revalidates and allocates weights. This matches PYNQ 2.7's requirement to establish overlay memory metadata before allocation. Regression checks cover a clean board state, invalid weights before any PL change, and a file changed between validation and allocation.

The user's latest instruction is to retain original HLS. No source fixes or inference gates are present. Static observations remain in the audit and do not replace the user's report that the existing implementation works.

Build input preservation fix: each new Vivado output contains a workspace copy. Offline Tcl execution with mocked Vivado entry commands verified all 253 prepared file hashes remain unchanged, including the 251 required source files. This is not a Vivado synthesis test.

Latest installation state: found the exact 244,664,096-byte Windows EXE under E:/Download, copied it to D:/software and verified Authenticode (Xilinx, Inc). SHA256 ddcea24a734b2727d152703c784bd822195a5898333cfc8c5041a92eadd6ea36. Extracted the client under D:/software/amd_2025_2_installer. The official bin/xsetup.bat -h returned an explicit administrator-permission error. The GUI was opened but no installation started; it has exited. Per the user's foreground preference, no further UI activation or elevation prompts are issued. Read-only readiness results: installer_readiness.json.
