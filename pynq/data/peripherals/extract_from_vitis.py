"""Re-extract exact sensor, autofocus, touch and font data from the supplied C.

Run on the development computer; no hardware access is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def initializer(source, symbol):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    match = re.search(r"\b" + re.escape(symbol) + r"\s*(?:\[[^\]]*\])+\s*=\s*\{(.*?)\};", source, re.S)
    if not match:
        raise ValueError("Missing initializer: " + symbol)
    tokens = re.findall(r"0[xX][0-9a-fA-F]+|\b\d+\b|'[^']'", match.group(1))
    return [ord(t[1]) if t.startswith("'") else int(t, 0) for t in tokens]


def extract(source_dir, destination):
    destination.mkdir(parents=True, exist_ok=True)
    specs = [
        ("OV5640/OV5640.h", "Reg_Init", "ov5640_registers.json", None),
        ("OV5640/OV5640.c", "OV5640_AF_Firmware", "ov5640_af.bin", 4077),
        ("LCD/lcd.c", "GT911_CFG_TBL", "gt911_config.bin", 184),
        ("LCD/font.h", "asc2_1206", "font12.bin", 95 * 12),
        ("LCD/font.h", "asc2_1608", "font16.bin", 95 * 16),
        ("LCD/font.h", "asc2_2412", "font24.bin", 95 * 36),
        ("LCD/font.h", "asc2_3216", "font32.bin", 95 * 64),
    ]
    manifest = {"source": "original/vitis_trash/Trash_LCD_OV5640/Lib", "files": {}}
    for relative, symbol, name, expected in specs:
        path = source_dir / relative
        source = path.read_bytes()
        values = initializer(source.decode("utf-8-sig"), symbol)
        if expected is not None and len(values) != expected:
            raise ValueError("Unexpected {} length: {} != {}".format(symbol, len(values), expected))
        if name.endswith(".json"):
            if len(values) % 2:
                raise ValueError("Odd register initializer")
            pairs = list(zip(values[::2], values[1::2]))
            payload = (json.dumps(pairs, indent=2) + "\n").encode()
        else:
            payload = bytes(values)
        (destination / name).write_bytes(payload)
        manifest["files"][name] = {"source_file": relative, "symbol": symbol,
            "source_sha256": hashlib.sha256(source).hexdigest(), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(), "initializer_elements": len(values)}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[3] / "original/vitis_trash/Trash_LCD_OV5640/Lib")
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(extract(args.source, args.destination), indent=2))
