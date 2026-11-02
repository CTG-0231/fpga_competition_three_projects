"""Host tests: C golden preprocessing, exact export validation, PL scheduling.

Run with ``python -m unittest discover -s sim -p test_model.py -v``.
These tests do not emulate HLS arithmetic or claim board-level validation.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

PORT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT_ROOT / "src"))
from trash_pynq.model import (CONFIGS, LABELS, NO_LEAF_LABEL, NO_LEAF_THRESHOLD,
                              MobileNetRunner, classify, load_weights,
                              preprocess_bgr, weight_specs)


def _cleanup_completed_process_directory(temporary):
    """Retry only transient Windows sharing violations after subprocess waits."""
    for attempt in range(6):
        try:
            temporary.cleanup()
            return
        except OSError as error:
            if (sys.platform != "win32" or getattr(error, "winerror", None) != 32
                    or attempt == 5):
                raise
            time.sleep(0.05 * (attempt + 1))


class DeviceBuffer(np.ndarray):
    def __new__(cls, shape, dtype, address):
        obj = np.empty(shape, dtype=dtype).view(cls)
        obj._root_address = address
        obj._root_pointer = obj.ctypes.data
        obj.flushes = 0
        obj.freed = False
        return obj

    def __array_finalize__(self, parent):
        if parent is not None:
            self._root_address = getattr(parent, "_root_address", 0)
            self._root_pointer = getattr(parent, "_root_pointer", self.ctypes.data)
            self.flushes = getattr(parent, "flushes", 0)
            self.freed = getattr(parent, "freed", False)

    @property
    def device_address(self):
        return self._root_address + self.ctypes.data - self._root_pointer

    def flush(self):
        self.flushes += 1

    def freebuffer(self):
        self.freed = True


class Allocator:
    def __init__(self):
        self.buffers = []

    def __call__(self, shape, dtype):
        buffer = DeviceBuffer(shape, dtype, 0x10000000 + len(self.buffers) * 0x400000)
        self.buffers.append(buffer)
        return buffer


class CheckedKernels:
    """Validate DMA sizes/address-preserving views at every scheduled kernel."""
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at
        self.conv_inputs = []

    def _call(self, mode, *buffers):
        for buffer in buffers:
            assert isinstance(buffer, DeviceBuffer)
            assert buffer.dtype == np.int16
            assert buffer.flags.c_contiguous
            assert buffer.device_address != 0
        self.calls.append(mode)
        if len(self.calls) == self.fail_at:
            raise TimeoutError("synthetic PL timeout")

    def conv(self, inp, weight, bias, out):
        self._call("conv", inp, weight, bias, out)
        assert inp.size == 3 * 224 * 224
        assert weight.size == 32 * 3 * 3 * 3
        assert bias.size == 32
        assert out.size == 32 * 112 * 112
        self.conv_inputs.append(inp.copy())
        out.fill(1)

    def pw(self, inp, weight, bias, out, ch_in, ch_out, act, size):
        self._call("pw", inp, weight, bias, out)
        assert inp.size == ch_in * size * size
        assert weight.size == ch_in * ch_out
        assert bias.size == ch_out
        assert out.size == ch_out * size * size
        assert act in (0, 1)
        out.fill(len(self.calls))

    def dw(self, inp, weight, bias, out, channel, size, stride):
        self._call("dw", inp, weight, bias, out)
        assert inp.size == channel * size * size
        assert weight.size == channel * 9
        assert bias.size == channel
        assert out.size == channel * (size // stride) ** 2
        assert stride in (1, 2)
        out.fill(len(self.calls))

    def shortcut(self, inp1, inp2, out, length):
        self._call("shortcut", inp1, inp2, out)
        assert inp1.size == inp2.size == out.size == length
        assert not np.shares_memory(inp1, out)
        assert not np.shares_memory(inp2, out)
        out[:] = inp1 + inp2

    def fc(self, inp, weight, bias, out):
        self._call("fc", inp, weight, bias, out)
        assert inp.size == 1280 * 7 * 7  # pooling is inside the original FC IP
        assert weight.size == 1280 * 6
        assert bias.size == 6
        assert out.size >= 8  # reserve complete 64-bit write beats
        out[:6] = [-17, 11, 300, -2, 6, 90]


def synthetic_weights(allocator):
    weights = {}
    for filename, count in weight_specs().items():
        buffer = allocator(shape=(count,), dtype="int16")
        buffer.fill(0)
        buffer.flush()
        weights[filename] = buffer
    return weights


class ModelTests(unittest.TestCase):
    def test_preprocess_boundaries_channels_and_negative_truncation(self):
        frame = np.zeros((224, 224, 3), np.uint8)
        frame[0, 0] = [255, 128, 1]
        actual = preprocess_bgr(frame)
        self.assertEqual(actual.shape, (3, 224, 224))
        self.assertEqual(actual.dtype, np.int16)
        self.assertTrue(actual.flags.c_contiguous)
        # R=1 gives -1015, not Python floor's -1016; G first becomes 100.
        np.testing.assert_array_equal(actual[:, 0, 0], [-1015, -220, 1024])
        np.testing.assert_array_equal(actual[:, 1, 1], [-1024] * 3)
        white = np.full((224, 224, 3), 255, np.uint8)
        np.testing.assert_array_equal(preprocess_bgr(white)[:, 0, 0], [1024, 574, 1024])
        np.testing.assert_array_equal(preprocess_bgr(white, 256, 256)[:, 0, 0], [1024] * 3)

    def test_preprocess_against_original_c_expressions_all_256_values(self):
        compiler = shutil.which("gcc")
        if compiler is None:
            candidate = Path(r"D:\environment\mingw64\bin\gcc.exe")
            compiler = str(candidate) if candidate.is_file() else None
        if compiler is None:
            self.skipTest("GCC unavailable; hand-calculated boundaries still tested")
        temporary = tempfile.TemporaryDirectory(dir=str(PORT_ROOT / "sim"))
        folder = temporary.name
        try:
            source = Path(folder) / "golden.c"
            binary = Path(folder) / ("golden.exe" if sys.platform == "win32" else "golden")
            source.write_text(
                '#include <stdio.h>\n'
                'int main(void) {\n'
                '  for (int v=0; v<256; ++v) {\n'
                '    int green=(v*200)/256;\n'
                '    short q=(short)((v*2048-255*1024)/255);\n'
                '    short g=(short)((green*2048-255*1024)/255);\n'
                '    printf("%d %d %d\\n",q,g,q);\n'
                '  }\n'
                '  float values[]={-32.0f,-1.9999f,-0.1f,0.0f,0.1f,1.9999f,31.999f};\n'
                '  for(int i=0;i<7;++i) printf("%d\\n",(short)(values[i]*1024));\n'
                '  return 0;\n}\n', encoding="ascii")
            compiler_env = dict(os.environ, TMP=folder, TEMP=folder)
            subprocess.run([compiler, "-std=c99", "-O2", str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True, env=compiler_env)
            lines = subprocess.check_output([str(binary)], text=True).splitlines()
        finally:
            # run/check_output both wait for their child before returning or
            # raising. A scanner may briefly retain golden.exe afterwards.
            _cleanup_completed_process_directory(temporary)
        golden = np.array([[int(v) for v in row.split()] for row in lines[:256]], np.int16)
        gray = (np.arange(224 * 224).reshape(224, 224) % 256).astype(np.uint8)
        frame = np.stack([gray, gray, gray], axis=-1)
        np.testing.assert_array_equal(preprocess_bgr(frame), golden[gray].transpose(2, 0, 1))
        values = np.array([-32.0, -1.9999, -0.1, 0.0, 0.1, 1.9999, 31.999], np.float32)
        quantized = np.trunc(values * np.float32(1024)).astype(np.int16)
        np.testing.assert_array_equal(quantized, np.array([int(v) for v in lines[256:]], np.int16))

    def test_preprocess_rejects_ambiguous_input(self):
        with self.assertRaises(ValueError):
            preprocess_bgr(np.zeros((224, 224, 3), np.float32))
        with self.assertRaises(ValueError):
            preprocess_bgr(np.zeros((480, 640, 3), np.uint8))
        with self.assertRaises(ValueError):
            preprocess_bgr(np.zeros((224, 224, 3), np.uint8), 1, 0)

    def test_configs_and_labels_match_original_sources(self):
        original = PORT_ROOT.parent / "original/vitis_trash/Trash_LCD_OV5640"
        if not original.is_dir():
            self.skipTest("original source not included in deployed package")
        content = (original / "Lib/Net/inference.c").read_text(encoding="utf-8")
        table = re.search(r"Cfg_q cfg\[16\]=\{(.*?)\};", content, re.S).group(1)
        parsed = [tuple(map(int, row.split(","))) for row in re.findall(r"\{([\d,]+)\}", table)]
        self.assertEqual(tuple(CONFIGS), tuple(parsed))
        mess = (original / "src/mess.c").read_text(encoding="utf-8")
        labels = re.search(r"char trash\[num_class\]\[100\]=\{(.*?)\};", mess).group(1)
        self.assertEqual(LABELS, tuple(re.findall(r'"([^"]+)"', labels)))

    def test_classify_applies_no_leaf_threshold(self):
        self.assertEqual(classify([0, 4000, -1, -2, -3, -4]),
                         (1, "bacterial_leaf_blight"))
        self.assertEqual(classify([0, 3999, -1, -2, -3, -4]), (None, NO_LEAF_LABEL))
        self.assertEqual(classify([NO_LEAF_THRESHOLD] * 6), (0, LABELS[0]))
        self.assertEqual(classify([NO_LEAF_THRESHOLD - 1] * 6), (None, NO_LEAF_LABEL))
        self.assertEqual(classify([-5000, 100, 200, 300, 400, 500]), (None, NO_LEAF_LABEL))
        self.assertEqual(classify([5000, 100, 200, 300, 400, 4500]), (0, LABELS[0]))
        with self.assertRaises(ValueError):
            classify([0, 1, 2])
        with self.assertRaises(ValueError):
            classify([0] * 6, threshold=float('nan'))

    def test_missing_weights_are_all_reported_before_allocation(self):
        allocator = Allocator()
        with tempfile.TemporaryDirectory(dir=str(PORT_ROOT / "sim")) as folder:
            with self.assertRaises(ValueError) as raised:
                load_weights(folder, allocator)
        for filename in weight_specs():
            self.assertIn(filename, str(raised.exception))
        self.assertEqual(len(weight_specs()), 106)
        self.assertEqual(allocator.buffers, [])

    def test_weight_float32_conversion_and_validation(self):
        allocator = Allocator()
        with tempfile.TemporaryDirectory(dir=str(PORT_ROOT / "sim")) as folder:
            directory = Path(folder)
            for filename, count in weight_specs().items():
                values = np.resize(np.array([-0.1, 0.1, 0, 31.999], dtype="<f4"), count)
                values.tofile(str(directory / filename))
            weights = load_weights(directory, allocator)
            for buffer in weights.values():
                self.assertEqual(buffer.flushes, 2)
                np.testing.assert_array_equal(buffer[:4], [-102, 102, 0, 32766])

            class FailingAllocator(Allocator):
                def __call__(self, shape, dtype):
                    if len(self.buffers) == 3:
                        raise MemoryError("synthetic CMA exhaustion")
                    return super().__call__(shape, dtype)

            failing = FailingAllocator()
            with self.assertRaises(MemoryError):
                load_weights(directory, failing)
            self.assertEqual(len(failing.buffers), 3)
            self.assertTrue(all(b.freed for b in failing.buffers))
            (directory / "head.wc1.bin").write_bytes(b"wrong length")
            np.full(32, np.nan, dtype="<f4").tofile(str(directory / "head.bc1.bin"))
            np.full(6, 32.0, dtype="<f4").tofile(str(directory / "tail.bf1.bin"))
            allocator2 = Allocator()
            with self.assertRaises(ValueError) as raised:
                load_weights(directory, allocator2)
            for diagnostic in ("head.wc1.bin", "head.bc1.bin", "tail.bf1.bin", "NaN", "range"):
                self.assertIn(diagnostic, str(raised.exception))
            self.assertEqual(allocator2.buffers, [])

    def test_complete_schedule_shapes_reuse_and_cpu_owned_scores(self):
        weight_allocator, activation_allocator = Allocator(), Allocator()
        weights = synthetic_weights(weight_allocator)
        kernels = CheckedKernels()
        runner = MobileNetRunner(kernels, activation_allocator, weights)
        for buffer in activation_allocator.buffers:
            self.assertEqual(buffer.flushes, 1)
            self.assertFalse(np.any(buffer))
        image = np.arange(3 * 224 * 224, dtype=np.int16).reshape(3, 224, 224)
        scores = runner.run(image)
        np.testing.assert_array_equal(scores, [-17, 11, 300, -2, 6, 90])
        self.assertEqual(kernels.calls.count("conv"), 1)
        self.assertEqual(kernels.calls.count("pw"), 34)
        self.assertEqual(kernels.calls.count("dw"), 17)
        self.assertEqual(kernels.calls.count("shortcut"), 10)
        self.assertEqual(kernels.calls.count("fc"), 1)
        self.assertEqual(len(kernels.calls), 63)
        np.testing.assert_array_equal(kernels.conv_inputs[0], image.reshape(-1))
        runner.run(image.reshape(-1))
        self.assertEqual(len(activation_allocator.buffers), 7)
        runner._output.fill(-999)
        np.testing.assert_array_equal(scores, [-17, 11, 300, -2, 6, 90])
        runner.close()
        self.assertTrue(all(b.freed for b in activation_allocator.buffers))
        self.assertTrue(all(not b.freed for b in weight_allocator.buffers))
        runner.close()
        with self.assertRaises(RuntimeError):
            runner.run(image)

    def test_dma_timeout_retains_buffers_until_explicit_reset_acknowledgment(self):
        allocator = Allocator()
        weights = synthetic_weights(Allocator())
        runner = MobileNetRunner(CheckedKernels(fail_at=2), allocator, weights)
        with self.assertRaises(TimeoutError):
            runner.run(np.zeros((3, 224, 224), np.int16))
        with self.assertRaises(RuntimeError):
            runner.close()
        self.assertTrue(all(not b.freed for b in allocator.buffers))
        with self.assertRaises(RuntimeError):
            runner.run(np.zeros((3, 224, 224), np.int16))
        runner.close(assume_hardware_stopped=True)
        self.assertTrue(all(b.freed for b in allocator.buffers))


if __name__ == "__main__":
    unittest.main()
