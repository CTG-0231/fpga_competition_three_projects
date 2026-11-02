import importlib.util
from pathlib import Path
import tempfile
import unittest

from trash_pynq.overlay import inspect_overlay, load_overlay

ROOT = Path(__file__).resolve().parents[1]


class OverlayTests(unittest.TestCase):
    def test_both_xsa_pairs_and_register_contract(self):
        for variant in ['3v3', '1v8']:
            manifest=inspect_overlay(ROOT / 'board/overlays' / variant)
            self.assertEqual(manifest['part'], 'xc7z020clg484-2')
            self.assertEqual(manifest['vivado_version'], '2019.2')

    def test_board_and_variant_checked_before_pynq_import(self):
        with self.assertRaises(ValueError):
            load_overlay(ROOT/'board/overlays/3v3', 'pynq-z2', '3.3')
        with self.assertRaises(ValueError):
            load_overlay(ROOT/'board/overlays/3v3', 'ac820', '1.8')

    def test_corrupted_hwh_rejected(self):
        import shutil
        tmp_root = ROOT / 'sim' / '.tmp'
        tmp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(tmp_root)) as tmp:
            out=Path(tmp)
            for name in ['leaf.bit','leaf.hwh','manifest.json']:
                shutil.copyfile(str(ROOT/'board/overlays/3v3'/name),str(out/name))
            with (out/'leaf.hwh').open('ab') as stream:
                stream.write(b'corruption')
            with self.assertRaises(ValueError):
                inspect_overlay(out)


if __name__=='__main__':
    unittest.main()
