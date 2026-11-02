"""Actual packaged weights and complete scheduling, without emulating PL maths."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from trash_pynq.model import load_weights, weight_specs, MobileNetRunner
from test_model import Allocator, CheckedKernels


class PackageAssetsTests(unittest.TestCase):
    def test_exact_case_and_all_106_weight_hashes(self):
        directory = ROOT/'data/trash_weight'
        specs = weight_specs()
        # Check actual directory strings; Windows open() alone cannot catch a
        # Linux-only filename case mismatch.
        self.assertEqual(set(specs), {p.name for p in directory.glob('*.bin')})
        self.assertTrue(all(name == name.lower() for name in specs))
        records = json.loads((ROOT/'data/model_manifest.json').read_text(encoding='utf-8'))['files']
        self.assertEqual(len(records), 106)
        self.assertEqual(set(specs), {r['name'] for r in records})
        for record in records:
            data = (directory/record['name']).read_bytes()
            self.assertEqual(len(data), specs[record['name']]*4)
            self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])

    def test_real_weights_are_consumed_by_all_63_calls(self):
        wa, aa = Allocator(), Allocator()
        weights = load_weights(ROOT/'data/trash_weight', wa)
        kernels = CheckedKernels()
        runner = MobileNetRunner(kernels, aa, weights)
        try:
            scores = runner.run(np.zeros((3, 224, 224), dtype=np.int16))
            self.assertEqual(len(weights), 106)
            self.assertEqual(len(kernels.calls), 63)
            np.testing.assert_array_equal(scores, [-17, 11, 300, -2, 6, 90])
        finally:
            runner.close()
            for buffer in weights.values():
                buffer.freebuffer()

    def test_board_launcher_resolves_project_and_compiles_every_stage(self):
        spec = importlib.util.spec_from_file_location('packaging_lanuch', ROOT/'board/lanuch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        self.assertEqual(launcher._find_root(), ROOT)
        self.assertEqual(set(launcher._load_stages(ROOT)), set(launcher._STAGES))


if __name__ == '__main__':
    unittest.main()
