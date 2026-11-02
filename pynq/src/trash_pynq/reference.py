"""CPU references for packed layout, saturated Q10 MAC, shortcut, and FC.

These mirror the ORIGINAL supplied HLS arithmetic, including its saturated
pooling reduction tree and quantized reciprocal. They are component references,
not a complete MobileNet or proof of board equivalence. HLS sources are unedited.
"""

import numpy as np


def pack_chw(chw):
    """CHW int16 -> flat [C/4,H,W,4], lane zero in lowest 16 AXI bits."""
    chw = np.asarray(chw)
    if chw.dtype != np.int16 or chw.ndim != 3 or chw.shape[0] % 4:
        raise ValueError("expected int16 CHW with channels divisible by four")
    channels, height, width = chw.shape
    return np.ascontiguousarray(chw.reshape(channels // 4, 4, height, width)
                               .transpose(0, 2, 3, 1)).reshape(-1)


def unpack_chw(packed, channels, height, width):
    """Flat packed int16 -> independent contiguous CHW array."""
    packed = np.asarray(packed)
    if (packed.dtype != np.int16 or channels % 4 or
            packed.size != channels * height * width):
        raise ValueError("packed buffer size/type does not match C,H,W")
    return np.ascontiguousarray(packed.reshape(channels // 4, height, width, 4)
                               .transpose(0, 3, 1, 2)).reshape(channels, height, width)


def _saturate(value):
    return np.clip(value, -32768, 32767).astype(np.int16)


def multiply_q10(left, right):
    """AP_RND (nearest; ties toward +infinity) then AP_SAT to Q6.10."""
    product = np.asarray(left, np.int64) * np.asarray(right, np.int64)
    return _saturate((product + 512) // 1024)


def mac_q10(accumulator, left, right):
    """One HLS ``data_t accumulator += left * right`` assignment."""
    product = np.asarray(left, np.int64) * np.asarray(right, np.int64)
    summed = np.asarray(accumulator, np.int64) + (product + 512) // 1024
    return _saturate(summed)


def shortcut_q10(left, right):
    left, right = np.asarray(left), np.asarray(right)
    if left.dtype != np.int16 or right.dtype != np.int16 or left.shape != right.shape:
        raise ValueError("shortcut inputs must be equal-shape int16 arrays")
    if left.size % 4:
        raise ValueError("original shortcut processes only full four-lane words")
    return _saturate(left.astype(np.int64) + right.astype(np.int64))


def avgpool_fc_q10(packed_input, weights, bias):
    """Original fc.cpp: packed 1280x7x7 -> six int16 logits.

    This deliberately preserves each saturated tree addition, reciprocal
    21/1024, bias-first accumulation, and per-channel MAC rounding/saturation.
    """
    feature = unpack_chw(packed_input, 1280, 7, 7).reshape(1280, 49).astype(np.int64)
    weights, bias = np.asarray(weights), np.asarray(bias)
    if weights.dtype != np.int16 or weights.size != 6 * 1280:
        raise ValueError("FC weights must contain 6*1280 int16 values")
    if bias.dtype != np.int16 or bias.size != 6:
        raise ValueError("FC bias must contain six int16 values")
    weights = weights.reshape(6, 1280)

    def add(a, b):
        return np.clip(a + b, -32768, 32767)

    p1 = add(feature[:, :24], feature[:, 24:48])
    p2 = add(p1[:, :12], p1[:, 12:24])
    p3 = add(p2[:, :6], p2[:, 6:12])
    p4 = add(p3[:, :3], p3[:, 3:6])
    p5a = add(p4[:, 0], p4[:, 1])
    p5b = add(p4[:, 2], feature[:, 48])
    # The final addition is an expression with AP fixed-width growth, not an
    # assignment to data_t. It can reach almost 64 before the multiplication.
    pooled = multiply_q10(p5a + p5b, np.int16(21))
    output = bias.reshape(6).copy()
    for channel in range(1280):
        output = mac_q10(output, pooled[channel], weights[:, channel])
    return output
