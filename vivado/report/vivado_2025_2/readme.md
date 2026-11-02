# Vivado 2025.2 implementation evidence, 2026-10-30

For a new reproduction, follow the [project README](../../README.md): restore
the `.bin` object snapshot and build the restored `p/leaf.xpr` before exporting
a new XSA. The evidence below remains historical; it is not a new run of that
workflow. The build.py entry mentioned below is the separate reintegration
route for newly rebuilt HLS IPs, not the native_2025_2 XPR entry.

The actual final four 2025.2 HLS exports completed synthesis, implementation,
bitstream and matching XSA export on the first normal build, exit 0 at 22:36:02.
See `final_summary.json` for immutable artifact hashes and `timing_review.md`
for the important coverage limits. The reproducible entry is
`../../build/vivado_2025_2/build.py` and its readme. This is not physical-board
validation or a complete FPGA network-inference result.

The first compatibility stage retained the original HLS RTL. It established
system-IP loading, RGB565/RGB888 widths and source isolation, but does not count
as a full HLS upgrade. Native PS7/video-output OOC processes crashed after
synthesis on their first attempt, then both succeeded on a recorded retry.
Top synthesis later reported out-of-memory before implementation. The logs are
retained; a separately observed concurrent HLS VIP peak is a possible resource
factor, not a proven crash cause.

Four actual 2025.2 candidate packages loaded and generated HWH. The first
post-generation external Python call failed because Vivado's PYTHONHOME/path
selected its bundled standard library; the scripts now invoke external Python
with `-I -X utf8 -B`. A subsequent isolated gate passed.

The new packages expose optional ID pins by default, unlike the original BD
instances. The reviewed official `C_M_AXI_*_ENABLE_ID_PORTS=false` instance
configuration restored the original physical boundary without modifying HDL or
IP-XACT. The real load-only probe checked 17 parameters, 85 generated wrapper
bindings (34 response-ID inputs tied to zero and 51 unused ID outputs), 265
staged file hashes, 101 actual HLS source hashes and all 44 XCI generation
directories. Original effective address spaces, register segments and DDR
windows remain equal. Added serialization metadata is recorded separately;
these checks do not establish full internal RTL equivalence.

The earlier load-only probe included an obsolete conv candidate and an initial pwdwconv
candidate with failed numerical tests. It is evidence for migration mechanics
only. Its old `progress_snapshot.json` is retained as history. The final
conv_cache/pwdw_scalarcopy3/fc/shortcut packages were separately frozen and
checked against the HLS numerical manifest: all 101 actually used generated
RTL files match the tested bytes (`final_hls_numeric_provenance.json`).
The final input gate, net connectivity, source paths, address ranges and
wrapper ties also passed. XSA-contained bit/HWH bytes match standalone files.

The two resume-only guard corrections were made after the successful normal
build: reject recorded live child PIDs even after interruption, and require
actual write_bitstream completion plus a nonempty bit file. Python state mocks
and Tcl interpreter tests without Tk/GUI passed; no AMD resume is claimed.
The actual first-build script hashes are preserved separately. No physical
board has been tested by this work.
