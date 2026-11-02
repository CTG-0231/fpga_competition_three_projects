"""Original folded MobileNetV2 schedule and its camera/weight contracts.

No PYNQ import is needed to inspect or test this module. Hardware kernels and
contiguous allocation are injected. The class owns its activation allocations;
weight buffers remain owned by the caller.
"""

from pathlib import Path
from typing import NamedTuple
from functools import wraps
from threading import Lock

import numpy as np


class BlockConfig(NamedTuple):
    ch_in: int
    ch_mid: int
    ch_out: int
    h: int
    w: int
    stride: int


CONFIGS = tuple(BlockConfig(*row) for row in (
    (16, 96, 24, 112, 112, 2),
    (24, 144, 24, 56, 56, 1),
    (24, 144, 32, 56, 56, 2),
    (32, 192, 32, 28, 28, 1),
    (32, 192, 32, 28, 28, 1),
    (32, 192, 64, 28, 28, 2),
    (64, 384, 64, 14, 14, 1),
    (64, 384, 64, 14, 14, 1),
    (64, 384, 64, 14, 14, 1),
    (64, 384, 96, 14, 14, 1),
    (96, 576, 96, 14, 14, 1),
    (96, 576, 96, 14, 14, 1),
    (96, 576, 160, 14, 14, 2),
    (160, 960, 160, 7, 7, 1),
    (160, 960, 160, 7, 7, 1),
    (160, 960, 320, 7, 7, 1),
))

LABELS = (
    "healthy", "bacterial_leaf_blight", "brown_spot", "leaf_blast",
    "leaf_scald", "narrow_brown",
)
INPUT_SHAPE = (3, 224, 224)
NUM_CLASSES = len(LABELS)

# A frame whose best raw Q10 score stays below this is not a recognisable leaf.
NO_LEAF_LABEL = "no_leaf"
NO_LEAF_THRESHOLD = 4000


def classify(scores, threshold=NO_LEAF_THRESHOLD):
    """Return ``(index, label)`` for one set of raw int16 Q10 scores.

    ``index`` is ``None`` when the best score is below ``threshold``; the label
    is then :data:`NO_LEAF_LABEL`. Scores stay raw hardware logits, so no
    probability is implied.
    """
    values = np.asarray(scores)
    if values.shape != (NUM_CLASSES,):
        raise ValueError("expected {} scores, got shape {}".format(NUM_CLASSES, values.shape))
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    best = int(np.argmax(values))
    if int(values[best]) < int(threshold):
        return None, NO_LEAF_LABEL
    return best, LABELS[best]


def _exclusive(method):
    @wraps(method)
    def invoke(self, *args, **kwargs):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('concurrent use of one runner is not supported')
        try:
            return method(self, *args, **kwargs)
        finally:
            self._lock.release()
    return invoke


def weight_specs():
    """Return ordered exact filename -> number of little-endian float32 values.

    Files contain hardware-specific folded/exported weights. Do not transpose,
    reblock, or regenerate these arrays from a generic MobileNet checkpoint.
    """
    specs = {
        "Head.Wc1.bin": 32 * 3 * 3 * 3,
        "Head.bc1.bin": 32,
        "Head.Wc2.bin": 32 * 9,
        "Head.bc2.bin": 32,
        "Head.Wc3.bin": 16 * 32,
        "Head.bc3.bin": 16,
    }
    for index, config in enumerate(CONFIGS):
        prefix = "FoldedInvertedResidual.{}.".format(index)
        specs.update({
            prefix + "Wc1.bin": config.ch_in * config.ch_mid,
            prefix + "bc1.bin": config.ch_mid,
            prefix + "Wc2.bin": config.ch_mid * 9,
            prefix + "bc2.bin": config.ch_mid,
            prefix + "Wc3.bin": config.ch_out * config.ch_mid,
            prefix + "bc3.bin": config.ch_out,
        })
    specs.update({
        "Tail.Wc1.bin": 1280 * 320,
        "Tail.bc1.bin": 1280,
        "Tail.Wf1.bin": 1280 * NUM_CLASSES,
        "Tail.bf1.bin": NUM_CLASSES,
    })
    return {name.lower(): count for name, count in specs.items()}


def _free(buffer):
    if hasattr(buffer, "freebuffer"):
        buffer.freebuffer()


def _allocate_zeroed(allocator, count):
    buffer = allocator(shape=(count,), dtype="int16")
    try:
        buffer.fill(0)
        buffer.flush()
    except BaseException:
        _free(buffer)
        raise
    return buffer


def _validated_weight_values(directory, retain_values):
    """Shared validation; retain conversions only for the subsequent loader."""
    directory = Path(directory)
    errors = []
    converted = {}
    for filename, count in weight_specs().items():
        path = directory / filename
        try:
            actual = path.stat().st_size
            expected = count * 4
            if actual != expected:
                errors.append("{}: expected {} bytes, got {}".format(
                    filename, expected, actual))
                continue
            values = np.fromfile(str(path), dtype="<f4")
            if values.size != count:
                errors.append("{}: changed while reading; expected {} values, got {}".format(
                    filename, count, values.size))
                continue
            with np.errstate(over="ignore", invalid="ignore"):
                scaled = np.trunc(values * np.float32(1024))
            if not np.all(np.isfinite(scaled)):
                errors.append("{}: contains NaN, infinity, or float32 overflow".format(filename))
                continue
            if np.any(scaled < -32768) or np.any(scaled > 32767):
                errors.append("{}: Q10 conversion exceeds signed int16 range".format(filename))
                continue
            if retain_values:
                converted[filename] = scaled.astype(np.int16)
        except FileNotFoundError:
            errors.append("{}: missing (expected {} bytes)".format(filename, count * 4))
        except OSError as exc:
            errors.append("{}: {}".format(filename, exc))
    if errors:
        raise ValueError("Invalid model weights in {}:\n{}".format(
            directory, "\n".join("- " + message for message in errors)))
    return converted


def validate_weights(directory):
    """Check every file, finite value and Q10 range without device allocation.

    No converted arrays are retained. This can run before a PYNQ overlay is
    downloaded; load_weights still reads and validates files independently.
    """
    _validated_weight_values(directory, retain_values=False)


def load_weights(directory, allocator):
    """Validate all 106 float32 files before allocating any device memory.

    Valid numbers are multiplied in float32 by 1024, then truncated toward zero,
    matching ``read_param_q`` for representable C ``short`` results. C behavior
    for out-of-range casts is not portable; reject such exports explicitly.
    Caller owns the returned buffers and must retain them while PL is active.
    """
    converted = _validated_weight_values(directory, retain_values=True)

    weights = {}
    try:
        for filename, values in converted.items():
            buffer = _allocate_zeroed(allocator, values.size)
            weights[filename] = buffer
            buffer[:] = values
            buffer.flush()
    except BaseException:
        for buffer in weights.values():
            _free(buffer)
        raise
    return weights


def preprocess_bgr(frame, green_gain_num=200, green_gain_den=256):
    """224x224 BGR uint8 -> contiguous RGB CHW int16, in [-1024, 1024].

    Both the gain and normalization exactly reproduce C integer division,
    including negative results truncating toward zero (Python // differs).
    No resize, crop, interpolation, gamma change, or float normalization occurs.
    """
    frame = np.asarray(frame)
    if frame.dtype != np.uint8 or frame.shape != (224, 224, 3):
        raise ValueError("frame must have shape (224, 224, 3) and dtype uint8 (BGR)")
    if (not isinstance(green_gain_num, (int, np.integer)) or
            not isinstance(green_gain_den, (int, np.integer)) or
            green_gain_num < 0 or green_gain_den <= 0 or
            green_gain_num > green_gain_den or green_gain_den > 2147483647):
        raise ValueError("green gain requires integers 0 <= numerator <= denominator <= 2147483647")
    rgb = frame[:, :, ::-1].transpose(2, 0, 1).astype(np.int64)
    rgb[1] = rgb[1] * int(green_gain_num) // int(green_gain_den)
    numerator = rgb * 2048 - 255 * 1024
    # Integer-only signed division avoids floor's -1 difference on negatives.
    quantized = np.where(numerator < 0, -((-numerator) // 255), numerator // 255)
    return np.ascontiguousarray(quantized, dtype=np.int16)


class MobileNetRunner:
    """Execute the original 63 kernel calls, reusing bounded CMA buffers.

    Kernel methods own cache synchronization and completion/timeout polling.
    An exception after a kernel starts may leave DMA active: this runner locks
    itself and retains all allocations. Reset/reload the overlay first, then
    explicitly call close(assume_hardware_stopped=True). Weights are caller-owned
    and must also be retained until hardware is known to have stopped.
    """

    def __init__(self, kernels, allocator, weights):
        self._lock = Lock()
        self.kernels = kernels
        self.weights = weights
        self._buffers = []
        self._closed = False
        self._faulted = False
        self._running = False
        errors = []
        for filename, count in weight_specs().items():
            buffer = weights.get(filename)
            if buffer is None:
                errors.append(filename + ": missing buffer")
            elif (np.dtype(buffer.dtype) != np.dtype("int16") or
                  buffer.size != count or not buffer.flags.c_contiguous or
                  not hasattr(buffer, "device_address")):
                errors.append(filename + ": expected contiguous int16 device buffer of length " + str(count))
        if errors:
            raise ValueError("Invalid device weight buffers:\n" + "\n".join(errors))

        def allocate(count):
            buffer = _allocate_zeroed(allocator, count)
            self._buffers.append(buffer)
            return buffer

        try:
            self._input = allocate(3 * 224 * 224)
            self._state_a = allocate(16 * 112 * 112)
            self._state_b = allocate(16 * 112 * 112)
            self._expand = allocate(96 * 112 * 112)
            self._depth = allocate(max(32 * 112 * 112, max(
                c.ch_mid * (c.h // c.stride) ** 2 for c in CONFIGS)))
            self._projection = allocate(24 * 56 * 56)
            # AXI writes may be wider than six int16 logits; reserve a full beat.
            self._output = allocate(8)
        except BaseException:
            for buffer in self._buffers:
                _free(buffer)
            self._closed = True
            raise

    def _weight(self, prefix, name):
        return self.weights[(prefix + "." + name + ".bin").lower()]

    @_exclusive
    def run(self, image_q):
        """Return a CPU-owned array of six raw signed Q10 logits."""
        if self._closed:
            raise RuntimeError("runner is closed")
        if self._faulted:
            raise RuntimeError("runner is faulted; reset the overlay before closing or recreating it")
        if self._running:
            raise RuntimeError("concurrent inference on one runner is not supported")
        image_q = np.asarray(image_q)
        if (image_q.dtype != np.int16 or
                image_q.shape not in (INPUT_SHAPE, (3 * 224 * 224,))):
            raise ValueError("image_q must be int16 RGB CHW of shape (3, 224, 224), or its flat equivalent")
        self._input[:] = image_q.reshape(-1)
        self._running = True
        try:
            k = self.kernels
            w = self._weight
            k.conv(self._input[:], w("Head", "Wc1"), w("Head", "bc1"),
                   self._expand[:32 * 112 * 112])
            k.dw(self._expand[:32 * 112 * 112], w("Head", "Wc2"), w("Head", "bc2"),
                 self._depth[:32 * 112 * 112], 32, 112, 1)
            k.pw(self._depth[:32 * 112 * 112], w("Head", "Wc3"), w("Head", "bc3"),
                 self._state_a[:16 * 112 * 112], 32, 16, 0, 112)
            current, target = self._state_a, self._state_b
            for index, config in enumerate(CONFIGS):
                prefix = "FoldedInvertedResidual.{}".format(index)
                size = config.h
                out_size = size // config.stride
                input_count = config.ch_in * size * size
                expand_count = config.ch_mid * size * size
                depth_count = config.ch_mid * out_size * out_size
                output_count = config.ch_out * out_size * out_size
                k.pw(current[:input_count], w(prefix, "Wc1"), w(prefix, "bc1"),
                     self._expand[:expand_count], config.ch_in, config.ch_mid, 1, size)
                k.dw(self._expand[:expand_count], w(prefix, "Wc2"), w(prefix, "bc2"),
                     self._depth[:depth_count], config.ch_mid, size, config.stride)
                residual = config.stride == 1 and config.ch_in == config.ch_out
                projected = self._projection if residual else target
                k.pw(self._depth[:depth_count], w(prefix, "Wc3"), w(prefix, "bc3"),
                     projected[:output_count], config.ch_mid, config.ch_out, 0, out_size)
                if residual:
                    k.shortcut(projected[:output_count], current[:input_count],
                               target[:output_count], output_count)
                current, target = target, current
            tail_count = 1280 * 7 * 7
            k.pw(current[:320 * 7 * 7], w("Tail", "Wc1"), w("Tail", "bc1"),
                 self._expand[:tail_count], 320, 1280, 1, 7)
            k.fc(self._expand[:tail_count], w("Tail", "Wf1"), w("Tail", "bf1"), self._output[:])
            return np.array(self._output[:NUM_CLASSES], dtype=np.int16, copy=True)
        except BaseException:
            # Conservative even for validation failures: the last PL state may
            # be unknown, and freeing CMA pages could corrupt another process.
            self._faulted = True
            raise
        finally:
            self._running = False

    @_exclusive
    def close(self, assume_hardware_stopped=False):
        """Free owned activations; faulted runners require prior hardware reset."""
        if self._closed:
            return
        if self._running:
            raise RuntimeError("cannot release buffers during inference")
        if self._faulted and not assume_hardware_stopped:
            raise RuntimeError("DMA may still be active; reset/reload the overlay, then close(assume_hardware_stopped=True)")
        for buffer in self._buffers:
            _free(buffer)
        self._buffers.clear()
        self._closed = True
