"""Apply three reviewed compatibility edits to an isolated BD copy only."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('bd', type=Path)
p.add_argument('report', type=Path)
a = p.parse_args()
source = a.bd.read_bytes()
tree = json.loads(source)
design = tree['design']
old = design['components']['v_vid_in_axi4s_0']
if old['vlnv'] != 'xilinx.com:ip:v_vid_in_axi4s:4.0':
    raise ValueError('Expected untouched 4.0 video input')
changes = []
def change(obj, key, value, path):
    before = obj.get(key)
    obj[key] = value
    changes.append({'path': path, 'before': before, 'after': value})
change(design['design_info'], 'gen_directory', 'generated', '/design/design_info/gen_directory')
change(old, 'vlnv', 'xilinx.com:ip:v_vid_in_axi4s:5.0', '/design/components/v_vid_in_axi4s_0/vlnv')
change(old['parameters'], 'C_VID_NATIVE_DE', {'value': '0'}, '/design/components/v_vid_in_axi4s_0/parameters/C_VID_NATIVE_DE')
result = (json.dumps(tree, indent=2) + '\n').encode('utf-8')
a.bd.write_bytes(result)
a.report.write_text(json.dumps({'source_sha256': hashlib.sha256(source).hexdigest(),
    'patched_sha256': hashlib.sha256(result).hexdigest(), 'changes': changes,
    'policy': 'Only isolated workspace BD modified; HLS algorithms and packaged RTL retained'}, indent=2) + '\n')
print('WORKSPACE_BD_COMPATIBILITY_PATCHED')
