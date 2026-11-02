"""Compile original HLS FC/shortcut and compare their raw Q10 results.

No HLS sources are modified. Uses installed vendor headers (not distributed).
Example on this workstation: python build/reference/check_components.py
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trash_pynq.reference import (avgpool_fc_q10, pack_chw, shortcut_q10,
                                 unpack_chw)


def check(compiler, include):
    compiler, include = Path(compiler), Path(include)
    if not compiler.is_file() or not (include / "ap_fixed.h").is_file():
        raise FileNotFoundError("C++ compiler and installed vendor ap_fixed.h are required")
    binary = ROOT / "build/reference" / ("hls_components.exe" if os.name == "nt" else "hls_components")
    command = [str(compiler), "-std=c++11", "-O2", "-I", str(include),
               str(ROOT / "build/reference/hls_components.cpp"),
               str(ROOT / "src/hls/avgpool_fc/fc.cpp"),
               str(ROOT / "src/hls/shortcut/shortcut.cpp"), "-o", str(binary)]
    env = dict(os.environ)
    env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
    env["TMP"] = env["TEMP"] = str(binary.parent)
    subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    run = subprocess.run([str(binary)], check=True, capture_output=True, text=True, env=env)
    actual = {line.split()[0]: [int(v) for v in line.split()[1:]]
              for line in run.stdout.splitlines()}
    lhs = np.array([32760, -32760, 1, -1, 30000, -30000, 512, -512], np.int16)
    rhs = np.array([100, -100, -1, 1, 30000, -30000, 512, -512], np.int16)
    expected = {"shortcut": shortcut_q10(lhs, rhs).tolist()}
    chw = np.full((1280, 7, 7), 6144, np.int16)
    weight, bias = np.zeros((6, 1280), np.int16), np.zeros(6, np.int16)
    weight[0, 0] = 1024
    weight[1, 1279] = 1024
    weight[2, :] = 1024
    weight[3, 0] = -1024
    bias[4] = 123
    weight[5, 0] = 512
    expected["fc_saturated"] = avgpool_fc_q10(pack_chw(chw), weight, bias).tolist()
    for channel in range(1280):
        chw[channel, :, :] = (channel * 17) % 1000 - 500
    np.testing.assert_array_equal(unpack_chw(pack_chw(chw), 1280, 7, 7), chw)
    weight = ((np.arange(6 * 1280, dtype=np.int64) * 7) % 100 - 50).astype(np.int16).reshape(6, 1280)
    bias = np.arange(6, dtype=np.int16) * 31 - 100
    expected["fc_packed_pattern"] = avgpool_fc_q10(pack_chw(chw), weight, bias).tolist()
    if expected != actual:
        raise AssertionError({"python": expected, "original_hls": actual})
    result = {
        "scope": "Original HLS FC/shortcut host components; not full network or board proof",
        "compiler": str(compiler), "vendor_headers": str(include),
        "actual_hls": actual, "python_integer_reference": expected, "all_equal": True,
        "hls_source_policy": "Original sources unedited; 12-file hashes in hls_source_integrity.json",
    }
    destination = ROOT / "report/hls_component_reference.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=shutil.which("g++") or r"D:\environment\mingw64\bin\g++.exe")
    parser.add_argument("--include", default=r"D:\software\X\Vivado\2018.3\include")
    args = parser.parse_args()
    print(json.dumps(check(args.compiler, args.include), indent=2))
