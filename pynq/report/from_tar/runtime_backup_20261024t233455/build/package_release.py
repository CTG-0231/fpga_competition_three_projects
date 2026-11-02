"""Package the reviewed port and prepared inputs; do not include raw datasets."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'output'


def selected_files():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel=path.relative_to(ROOT)
        if any(p in ('__pycache__','.tmp','.git') or p.startswith('tmp') for p in rel.parts):
            continue
        if 'work' in rel.parts:
            # Only original prepared inputs, never caches/old runs.
            if rel.parts[:3] != ('build','work','prepared'):
                continue
        if rel.suffix in ('.pyc','.exe','.o','.obj'):
            continue
        yield path,rel


if __name__=='__main__':
    OUTPUT.mkdir(exist_ok=True)
    target=OUTPUT/'ac820_pynq_port.zip'
    manifest={}
    with ZipFile(str(target),'w',ZIP_DEFLATED,compresslevel=6) as archive:
        for path,rel in selected_files():
            payload=path.read_bytes()
            manifest[rel.as_posix()]=hashlib.sha256(payload).hexdigest()
            archive.writestr('pynq_port/'+rel.as_posix(),payload)
        archive.writestr('pynq_port/release_checksums.json',json.dumps(manifest,indent=2)+'\n')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (OUTPUT/'ac820_pynq_port.zip.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    with ZipFile(str(target)) as check:
        damaged=check.testzip()
        if damaged is not None:
            raise RuntimeError('ZIP CRC failure: '+damaged)
        for name,expected in manifest.items():
            if hashlib.sha256(check.read('pynq_port/'+name)).hexdigest()!=expected:
                raise RuntimeError('ZIP checksum mismatch: '+name)
    print(json.dumps({'output':str(target),'files':len(manifest),'bytes':target.stat().st_size,
                      'sha256':digest,'zip_integrity':'passed','board_tested':False},indent=2))
