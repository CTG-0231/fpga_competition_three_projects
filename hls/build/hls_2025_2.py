"""Run preserved HLS algorithms with Vitis 2025.2 in an external workspace."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MODULES = {"conv": "conv", "pwdwconv": "pwdwconv", "fc": "avgpool_fc", "shortcut": "shortcut"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.now().astimezone().isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_sources(source, manifest):
    failures = [name for name, entry in manifest["files"].items()
                if not (source / name).is_file() or sha(source / name) != entry["sha256"]]
    if failures:
        raise RuntimeError("Original source SHA256 mismatch: " + ", ".join(failures))
    if sum(e["kind"] == "algorithm" for e in manifest["files"].values()) != 12:
        raise RuntimeError("Expected exactly 12 algorithm files")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New external directory; must not exist")
    parser.add_argument("--tool", type=Path, default=os.environ.get("VITIS_RUN"), help="2025.2 vitis-run.bat or vitis-run")
    parser.add_argument("--source", type=Path, default=ROOT / "src/kernels")
    parser.add_argument("--kernels", nargs="+", choices=list(MODULES), default=list(MODULES))
    parser.add_argument("--action", choices=["build", "csim", "cosim", "all"], default="build")
    parser.add_argument("--conv-dataflow", choices=["disable_legacy_pragma", "keep"], default="disable_legacy_pragma",
                        help="Generate a recorded compile-only copy, or reproduce the original 2025.2 error")
    parser.add_argument("--bias-copy", choices=["scalar_1280", "original"], default="scalar_1280",
                        help="Equivalent scalar bias copies and PW storage for model ch_out1280; canonical files retained")
    options = parser.parse_args()
    source, output = options.source.resolve(), options.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("Output must be outside the submitted source tree")
    if output.exists():
        parser.error("Use a fresh --output directory to preserve previous evidence")
    tool = options.tool or shutil.which("vitis-run") or shutil.which("vitis-run.bat")
    if not tool:
        parser.error("Provide --tool or VITIS_RUN for the real 2025.2 installation")
    tool = Path(tool).resolve()
    manifest = json.loads((ROOT / "report/hls_2025_2/source_manifest.json").read_text(encoding="utf-8"))
    verify_sources(source, manifest)
    output.mkdir(parents=True)
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["XILINX_LOCAL_USER_DATA"] = "no"  # Process-local empirical workaround, not an AMD fix.
    prefix = ["cmd.exe", "/d", "/c", str(tool)] if os.name == "nt" else [str(tool)]
    version = subprocess.run(prefix + ["--mode", "hls", "-v"], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    (output / "tool_version.log").write_text(version.stdout, encoding="utf-8")
    if version.returncode or "2025.2" not in version.stdout:
        raise RuntimeError("Tool version check failed; see tool_version.log")
    write_json(output / "source_manifest.json", manifest)
    results = []
    compile_changes = []
    for kernel in options.kernels:
        module = MODULES[kernel]
        canonical = output / "inputs" / module
        canonical.mkdir(parents=True)
        for name in manifest["files"]:
            if Path(name).parts[0] == module:
                shutil.copy2(source / name, canonical / Path(name).name)
        compiled = canonical
        differences = []
        if kernel == "conv" and options.conv_dataflow == "disable_legacy_pragma":
            compiled = output / "compile_inputs" / module
            shutil.copytree(canonical, compiled)
            path = compiled / "conv.cpp"
            raw = path.read_bytes()
            old = b"\t#pragma HLS DATAFLOW"
            new = b"\t// HLS2025.2 migration: legacy DATAFLOW at compute_output loop disabled."
            lines = raw.splitlines()
            if len(lines) < 85 or lines[84] != old or raw.count(old) != 1:
                raise RuntimeError("Expected unique legacy DATAFLOW at conv.cpp line 85")
            path.write_bytes(raw.replace(old, new))
            differences.append({"file": "conv/conv.cpp", "line": 85, "old": old.decode(), "new": new.decode(),
                                "canonical_sha256": sha(canonical / "conv.cpp"), "compiled_sha256": sha(path),
                                "reason": "Scheduling-only workaround for HLS200-994; original canonical source retained"})
        if kernel == "pwdwconv" and options.bias_copy == "scalar_1280":
            compiled = output / "compile_inputs" / module
            shutil.copytree(canonical, compiled)
            for filename, old, new, reason in [
                ("pwconv.cpp", b"memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*M);",
                 b"for (int bias_index = 0; bias_index < M; ++bias_index) { bias_buff[bias_index / Tm][bias_index % Tm] = bias[bias_index]; }",
                 "Equivalent per-element copy; avoid 2025.2 dynamic memcpy losing non-first partitioned bias rows"),
                ("dwconv.cpp", b"memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*channel);",
                 b"for (int bias_index = 0; bias_index < channel; ++bias_index) { bias_buff[bias_index / Tm][bias_index % Tm] = bias[bias_index]; }",
                 "Equivalent per-element copy; DW uses its own Tm=8 from dwconv.h"),
                ("pwconv.h", b"#define MAX_LEN 1024", b"#define MAX_LEN 1280",
                 "PW storage capacity covers the model final ch_out1280; arithmetic and quantization unchanged")
            ]:
                path = compiled / filename
                raw = path.read_bytes()
                if raw.count(old) != 1:
                    raise RuntimeError("Expected unique compatibility statement in " + filename)
                path.write_bytes(raw.replace(old, new))
                differences.append({"file": "pwdwconv/" + filename, "line": raw[:raw.index(old)].count(b"\n") + 1,
                                    "old": old.decode(), "new": new.decode(), "canonical_sha256": sha(canonical / filename),
                                    "compiled_sha256": sha(path), "reason": reason})
        compile_changes.extend(differences)
        write_json(output / "compile_source_diff.json", {"changes": compile_changes, "canonical_algorithms_preserved": 12})
        # Keep inputs outside work/: classic HLS can save wrong relative paths
        # when add_files sources sit below a run working directory.
        run = output / "work/runs" / kernel
        run.mkdir(parents=True)
        project = output / "work/projects" / kernel
        exported = output / "exported" / (kernel + ".zip")
        exported.parent.mkdir(exist_ok=True)
        config = run / "hls_config.cfg"
        task_env = env.copy()
        task_env.update(HLS_KERNEL=kernel, HLS_PROJECT=project.as_posix(), HLS_SOURCE_DIR=compiled.as_posix(),
                        HLS_TEST_DIR=canonical.as_posix(), HLS_EXPORT=exported.as_posix(),
                        HLS_CONFIG=config.as_posix(), HLS_ACTION=options.action)
        status = {"kernel": kernel, "action": options.action, "status": "running", "started_at": stamp(),
                  "project": str(project), "compile_source_differences": differences}
        write_json(run / "status.json", status)
        start = time.monotonic()
        with (run / "hls.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(prefix + ["--mode", "hls", "--tcl", str(ROOT / "build/hls_2025_2.tcl")],
                                    cwd=run, env=task_env, stdout=log, stderr=subprocess.STDOUT)
        verify_sources(source, manifest)
        for name, entry in manifest["files"].items():
            if Path(name).parts[0] == module and sha(canonical / Path(name).name) != entry["sha256"]:
                raise RuntimeError("Canonical input was modified: " + name)
        status.update(status="complete" if result.returncode == 0 else "failed", exit_code=result.returncode,
                      finished_at=stamp(), elapsed_seconds=round(time.monotonic() - start, 3))
        write_json(run / "status.json", status)
        results.append(status)
        write_json(output / "summary.json", {"runs": results, "original_12_algorithm_sha256_pass": True,
                                             "all_requested_actions_pass": all(r["exit_code"] == 0 for r in results)})
        print(kernel, status["status"], "log:", run / "hls.log", flush=True)
    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
