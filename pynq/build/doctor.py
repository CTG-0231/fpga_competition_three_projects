"""Read-only inventory. Does not download a bitstream or modify Linux settings."""
import argparse
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from trash_pynq.overlay import inspect_overlay
from trash_pynq.model import weight_specs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', choices=['3v3', '1v8'], default='3v3')
    p.add_argument('--overlay-dir', type=Path)
    p.add_argument('--weights', type=Path, default=ROOT / 'data/trash_weight')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    manifest = inspect_overlay(args.overlay_dir if args.overlay_dir is not None else ROOT / 'board/overlays' / args.variant)
    specs = weight_specs()
    missing, invalid = [], []
    for name, count in specs.items():
        path = args.weights / name
        if not path.is_file():
            missing.append(name)
        elif path.stat().st_size != count * 4:
            invalid.append(name)
    report = {
        'host': platform.platform(), 'python': platform.python_version(),
        'overlay_pair_integrity': 'passed', 'fpga_part': manifest['part'],
        'source_vivado': manifest['vivado_version'],
        'hls_policy': manifest.get('hls_policy'),
        'pynq_board_validation': 'pending',
        'weight_format': 'little-endian float32; quantize to int16 Q10',
        'weights_required': len(specs), 'weights_missing': missing,
        'weights_wrong_size': invalid,
        'board_execution': 'not_performed',
        'i2c_adapters': [],
        'cma': [],
    }
    sysfs = Path('/sys/class/i2c-adapter')
    if sysfs.exists():
        for item in sorted(sysfs.glob('i2c-*')):
            record = {'bus': item.name}
            for name in ['name', 'device/of_node/full_name']:
                path = item / name
                if path.is_file():
                    record[name] = path.read_bytes().rstrip(b'\0\n').decode(errors='replace')
            report['i2c_adapters'].append(record)
    meminfo = Path('/proc/meminfo')
    if meminfo.is_file():
        report['cma'] = [line for line in meminfo.read_text().splitlines() if line.startswith('Cma')]
    content = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    print(content)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    return 0 if not missing and not invalid else 2


if __name__ == '__main__':
    raise SystemExit(main())
