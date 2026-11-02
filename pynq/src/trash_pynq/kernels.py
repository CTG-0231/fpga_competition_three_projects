"""HLS MMIO calls matching the supplied 2019.2 generated drivers exactly."""
import math
import time
from threading import RLock
import numpy as np


class KernelTimeout(TimeoutError):
    """The PL may still be accessing memory: retain all buffer references."""


class Kernels:
    def __init__(self, overlay, timeout=5.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be finite and positive')
        self.overlay, self.timeout = overlay, timeout
        self.faulted = False
        self._pinned = []
        self._lock = RLock()
        self.trace = []
        # PYNQ 2.7 rebuilds a DefaultIP and its MMIO mapping on every attribute
        # access; on AC820 that costs ~26 ms per access, i.e. ~1.5 s for the 63
        # kernel calls. The four handles are static once the overlay is loaded,
        # so resolve them once here instead of inside every call.
        self._ips = {name: getattr(overlay, name) for name in (
            'conv_0', 'fc_0', 'pwdwconv_0', 'shortcut_0')}

    @staticmethod
    def address(buffer):
        if not isinstance(buffer, np.ndarray) or buffer.dtype != np.dtype('int16'):
            raise TypeError('HLS buffers must be PYNQ int16 arrays')
        if not buffer.flags.c_contiguous:
            raise ValueError('HLS buffers must be contiguous')
        address = getattr(buffer, 'device_address', None)
        if address is None:
            address = getattr(buffer, 'physical_address', None)
        if address is None or not all(callable(getattr(buffer, m, None))
                                      for m in ('flush', 'invalidate')):
            raise TypeError('Use pynq.allocate; NumPy virtual addresses are not DMA addresses')
        address = int(address)
        if address <= 0 or address % 8 or address + buffer.nbytes > 0x40000000:
            raise ValueError('Buffer must be 8-byte aligned in this HWH 1 GiB AXI window')
        return address

    def _run(self, name, pointers, scalars, inputs, output):
        with self._lock:
            if self.faulted:
                raise RuntimeError('Kernel is faulted; reboot/reload hardware before reuse')
            # Validate the entire call before touching hardware.
            values = [(offset, self.address(buf)) for offset, buf in pointers]
            ip = self._ips[name]
            for buffer in inputs:
                buffer.flush()
            # Clear stale dirty CPU cachelines before a PL write. PL-produced
            # buffers are invalidated immediately after every completed call.
            output.flush()
            status = ip.read(0x00)  # consume stale read-to-clear ap_done
            if not status & 6:
                raise RuntimeError('{} is already busy; do not overwrite active DMA pointers'.format(name))
            for offset, value in values + list(scalars):
                ip.write(offset, int(value))
            self._pinned = [buf for _, buf in pointers]
            started = time.monotonic()
            try:
                ip.write(0x00, 1)
                while True:
                    status = ip.read(0x00)
                    if status & 2:
                        break
                    if time.monotonic() - started >= self.timeout:
                        raise KernelTimeout('{} timed out, AP_CTRL=0x{:08x}; reboot before freeing buffers'.format(name, status))
                    time.sleep(0.0001)
                output.invalidate()
            except BaseException:
                self.faulted = True
                # Retain even when a notebook drops its local variable. A
                # timeout does not imply that the AXI masters have stopped.
                _FAULTED_KERNELS.append(self)
                raise
            self.trace.append({'ip': name, 'seconds': time.monotonic() - started})
            self._pinned = []

    def conv(self, source, weight, bias, output):
        if source.size < 3*224*224 or weight.size < 32*3*3*3 or bias.size < 32 or output.size < 32*112*112:
            raise ValueError('conv buffer too small')
        self._run('conv_0', [(0x10, source), (0x18, source), (0x20, source),
                            (0x28, weight), (0x30, bias), (0x38, output)], [],
                  [source, weight, bias], output)

    def pw(self, source, weight, bias, output, ch_in, ch_out, act, size):
        if min(ch_in, ch_out, size) <= 0 or act not in (0, 1):
            raise ValueError('Invalid pointwise configuration')
        if source.size < ch_in*size*size or weight.size < ch_in*ch_out or bias.size < ch_out or output.size < ch_out*size*size:
            raise ValueError('pw buffer too small')
        self._run('pwdwconv_0', [(0x10, source), (0x18, weight), (0x20, weight),
                                (0x28, output), (0x30, bias), (0x38, bias)],
                  [(0x40, ch_in), (0x48, ch_out), (0x50, 1), (0x58, size),
                   (0x60, act), (0x68, 1)], [source, weight, bias], output)

    def dw(self, source, weight, bias, output, channel, size, stride):
        if min(channel, size) <= 0 or stride not in (1, 2) or size % stride:
            raise ValueError('Invalid depthwise configuration')
        if source.size < channel*size*size or weight.size < channel*9 or bias.size < channel or output.size < channel*(size//stride)**2:
            raise ValueError('dw buffer too small')
        self._run('pwdwconv_0', [(0x10, source), (0x18, source), (0x20, output),
                                (0x28, output), (0x30, weight), (0x38, bias)],
                  [(0x40, channel), (0x48, channel), (0x50, stride),
                   (0x58, size), (0x60, 1), (0x68, 0)], [source, weight, bias], output)

    def shortcut(self, source1, source2, output, length):
        if length <= 0 or any(b.size < length for b in (source1, source2, output)):
            raise ValueError('shortcut buffer too small')
        self._run('shortcut_0', [(0x10, source1), (0x18, source2), (0x20, output)],
                  [(0x28, length)], [source1, source2], output)

    def fc(self, source, weight, bias, output):
        if source.size < 1280*7*7 or weight.size < 1280*6 or bias.size < 6 or output.size < 6:
            raise ValueError('fc buffer too small for fixed six-class hardware')
        self._run('fc_0', [(0x10, source), (0x18, weight), (0x20, bias), (0x28, output)],
                  [], [source, weight, bias], output)


_FAULTED_KERNELS = []
