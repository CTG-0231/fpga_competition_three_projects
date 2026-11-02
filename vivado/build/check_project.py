"""Read-only verification of this project's payload and source snapshots."""
from pathlib import Path
import hashlib, json, re, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_store import verify_snapshot, sha256_file
ROOT = Path(__file__).resolve().parents[1]
def main():
    required = ['src', 'sim', 'build', 'board', 'data', 'skill', 'report']
    errors = [name for name in required if not (ROOT / name).is_dir()]
    files = {}
    for p in ROOT.rglob('*'):
        rel = p.relative_to(ROOT)
        if '__pycache__' in rel.parts or p.suffix == '.pyc': continue
        if any(x != 'README.md' and not re.fullmatch('[a-z0-9_.-]+', x) for x in rel.parts):
            errors.append('Invalid path: ' + rel.as_posix())
        if p.is_file() and rel.as_posix() != 'release_checksums.json':
            files[rel.as_posix()] = sha256_file(p)
    expected = json.loads((ROOT / 'release_checksums.json').read_text())
    errors += [n for n in sorted(set(expected) | set(files)) if expected.get(n) != files.get(n)]
    counts = {}
    for group, record in json.loads((ROOT / 'src/source_catalog.json').read_text()).items():
        p = ROOT / record['archive']
        if sha256_file(p) != record['sha256']: errors.append('Corrupt snapshot ' + group)
        counts[group] = len(verify_snapshot(p)['files'])
    result = dict(passed=not errors, files=len(files), snapshot_files=counts, errors=errors,
                  hardware_execution=False)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1
if __name__ == '__main__': raise SystemExit(main())
