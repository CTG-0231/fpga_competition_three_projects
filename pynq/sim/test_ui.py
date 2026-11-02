"""Verify LCD layout, label presentation, hit targets and output orientation."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trash_pynq.ui import BUTTONS, LABEL_TEXT, LeafUI


class UITests(unittest.TestCase):
    def setUp(self):
        self.ui = LeafUI()

    def test_six_labels_render_without_mutating_camera(self):
        frame = np.arange(224 * 224 * 3, dtype=np.uint8).reshape(224, 224, 3)
        before = frame.copy()
        for label in LABEL_TEXT:
            result = self.ui.render(frame, label, latency_ms=128.3, saved_count=7)
            self.assertEqual(result.shape, (480, 800, 3))
            self.assertEqual(result.dtype, np.uint8)
            self.assertTrue(result.flags.c_contiguous)
        np.testing.assert_array_equal(frame, before)

    def test_touch_targets_match_drawn_buttons_and_half_open_edges(self):
        for action, (x, y, width, height) in BUTTONS.items():
            self.assertEqual(self.ui.hit_test(x + width // 2, y + height // 2), action)
            self.assertEqual(self.ui.hit_test(x, y), action)
            self.assertNotEqual(self.ui.hit_test(x + width, y + height), action)
        self.assertIsNone(self.ui.hit_test(10, 200))
        self.assertIsNone(self.ui.hit_test(400, 425))

    def test_output_rotation_is_exactly_once_and_render_is_independent(self):
        frame = self.ui.render()
        physical = self.ui.physical_frame(frame)
        np.testing.assert_array_equal(physical, frame[::-1, ::-1])
        self.assertTrue(physical.flags.c_contiguous)
        frame[:] = 0
        self.assertTrue(self.ui.physical_frame().any())

    def test_light_state_changes_only_the_light_button(self):
        off = self.ui.render(light=False)
        on = self.ui.render(light=True)
        x, y, width, height = BUTTONS["light"]
        changed = np.any(off != on, axis=2)
        self.assertTrue(changed[y:y + height, x:x + width].any())
        changed[y:y + height, x:x + width] = False
        self.assertFalse(changed.any())

    def test_invalid_image_or_prediction_fails(self):
        with self.assertRaises(ValueError):
            self.ui.render(np.zeros((224, 224, 3), dtype=np.float32))
        with self.assertRaises(ValueError):
            self.ui.render(label="unverified_label")
        with self.assertRaises(ValueError):
            self.ui.render(latency_ms=float("nan"))


def generate_previews():
    from PIL import Image
    directory = ROOT / "report"
    directory.mkdir(exist_ok=True)
    ui = LeafUI()
    ready = ui.render(status="Ready - tap Detect to begin")
    # Source frame supplied with the original Python project. The label and
    # latency below demonstrate layout only; no recognition claim is made.
    source = ROOT.parent / "original/python_trash/Out.bin"
    if not source.exists():
        raise FileNotFoundError("Original BGR camera sample required for preview: " + str(source))
    payload = source.read_bytes()
    if len(payload) != 224 * 224 * 3:
        raise ValueError("Original camera sample has the wrong dimensions")
    camera = np.frombuffer(payload, np.uint8).reshape(224, 224, 3)
    identified = ui.render(camera, "leaf_blast", latency_ms=128, light=True,
                           status="UI preview - example result", saved_count=12)
    for name, frame in (("lcd_ui_preview.png", ready), ("lcd_ui_preview_identified.png", identified)):
        Image.fromarray(frame[:, :, ::-1]).save(directory / name)
        print(directory / name)


if __name__ == "__main__":
    if "--preview" in sys.argv:
        generate_previews()
    else:
        unittest.main()
