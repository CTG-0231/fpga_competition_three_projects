"""Restore exact native filenames into a new directory outside this submission."""
from pathlib import Path
import argparse, json, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_store import restore_snapshot, sha256_file
ROOT = Path(__file__).resolve().parents[1]
def main():
    catalog = json.loads((ROOT / 'src/source_catalog.json').read_text(encoding='utf-8'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', required=True, choices=sorted(catalog))
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    record = catalog[args.group]
    path = ROOT / record['archive']
    if sha256_file(path) != record['sha256']:
        raise ValueError('Snapshot checksum mismatch')
    count = restore_snapshot(path, args.destination, ROOT.parent)
    print(json.dumps(dict(group=args.group, files=count, destination=str(args.destination.resolve()),
                          tool_build_executed=False, board_accessed=False)))
if __name__ == '__main__':
    main()
