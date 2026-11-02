"""AC820 original OV5640, GT911 and LCD drivers for PYNQ/Linux.

No PS registers or fixed DDR addresses are accessed. Linux must first expose
the original design's I2C0 (MIO50/51), I2C1 (EMIO) and GPIO pin configuration.
Imports and all pure image operations work without PYNQ installed.
"""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import xml.etree.ElementTree as ET

import numpy as np

# Keep a strong reference when a DMA channel may still own an allocation.
# Notebook exception tracebacks alone do not guarantee the object's lifetime.
_FAULTED_VIDEO = []
_ACTIVE_VIDEO = []


class PeripheralError(RuntimeError):
    pass


def _data_dir(directory=None):
    if directory is not None:
        return Path(directory)
    return Path(__file__).resolve().parents[2] / "data" / "peripherals"


def load_data(name, directory=None):
    """Check generated data against the manifest before programming a device."""
    directory = _data_dir(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    payload = (directory / name).read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest["files"][name]["sha256"]:
        raise PeripheralError("Peripheral data checksum mismatch: " + name)
    return payload


def raw_mmio(overlay, name):
    """Map an IP's registers without instantiating PYNQ's name-bound driver.

    PYNQ 2.7 binds ``axi_vdma_0`` to :class:`pynq.lib.video.dma.AxiVDMA`, whose
    constructor requires an ``s2mm_introut`` interrupt pin. The original Vitis
    design polls these registers and leaves the interrupts unconnected, so
    ``overlay.axi_vdma_0`` raises AttributeError. The original driver code is
    reproduced here, so build the mapping from ``ip_dict`` instead.
    """
    description = overlay.ip_dict[name]
    from pynq import MMIO
    return MMIO(description['phys_addr'], description['addr_range'],
                device=overlay.device)


class _I2CMessage(ctypes.Structure):
    _fields_ = [("addr", ctypes.c_uint16), ("flags", ctypes.c_uint16),
                ("length", ctypes.c_uint16), ("buf", ctypes.POINTER(ctypes.c_ubyte))]


class _I2CTransfer(ctypes.Structure):
    _fields_ = [("msgs", ctypes.POINTER(_I2CMessage)), ("nmsgs", ctypes.c_uint32)]


def discover_ps_i2c(controller, sysfs="/sys/class/i2c-dev"):
    """Match controller address, never assume Linux's i2c-N enumeration."""
    if controller not in (0, 1):
        raise ValueError("PS I2C controller must be 0 or 1")
    address = (0xE0004000, 0xE0005000)[controller]
    found = []
    for adapter in Path(sysfs).glob("i2c-*"):
        node = adapter / "device" / "of_node"
        try:
            reg = (node / "reg").read_bytes()
            # Zynq-7000 uses one address cell, one size cell.
            if len(reg) < 8 or int.from_bytes(reg[:4], "big") != address:
                continue
            clock_file = node / "clock-frequency"
            clock = int.from_bytes(clock_file.read_bytes(), "big") if clock_file.exists() else None
            found.append((int(adapter.name[4:]), clock))
        except (OSError, ValueError):
            continue
    if len(found) != 1:
        raise PeripheralError("Need exactly one Linux I2C adapter for PS I2C{} at 0x{:08x}; found {}. Configure device tree/pinctrl first.".format(controller, address, found))
    return found[0]


class LinuxI2C:
    """16-bit register transactions via i2c-dev with combined reads.

    I2C_SLAVE is used without FORCE, so kernel-owned devices remain protected.
    Clock speed comes from the device tree, not a userspace MMIO override.
    """
    def __init__(self, bus, *, frequency_hz=None, dev_root="/dev"):
        if os.name != "posix":
            raise PeripheralError("Linux i2c-dev is required on the target board")
        self.bus = int(bus)
        self.frequency_hz = frequency_hz
        self._lock = threading.RLock()
        self._fd = os.open(str(Path(dev_root) / ("i2c-" + str(bus))), os.O_RDWR)
        self._libc = ctypes.CDLL(None, use_errno=True)
        self._libc.ioctl.restype = ctypes.c_int

    @classmethod
    def for_ps_controller(cls, controller, *, bus=None, sysfs="/sys/class/i2c-dev"):
        discovered, frequency = discover_ps_i2c(controller, sysfs)
        if bus is not None and int(bus) != discovered:
            raise PeripheralError("Requested Linux bus does not match PS controller")
        return cls(discovered, frequency_hz=frequency)

    def _ioctl(self, request, argument):
        result = self._libc.ioctl(ctypes.c_int(self._fd), ctypes.c_ulong(request), argument)
        if result < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        return result

    def _transfer(self, address, payload, read_length=0):
        if not 0x08 <= address <= 0x77 or not 1 <= len(payload) <= 65535:
            raise ValueError("Invalid 7-bit I2C address or message length")
        if not 0 <= read_length <= 65535:
            raise ValueError("Invalid read length")
        if self._fd is None:
            raise PeripheralError("I2C adapter is closed")
        tx = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        rx = (ctypes.c_ubyte * read_length)()
        count = 2 if read_length else 1
        messages = (_I2CMessage * count)()
        messages[0] = _I2CMessage(address, 0, len(payload), tx)
        if read_length:
            messages[1] = _I2CMessage(address, 1, read_length, rx)
        transfer = _I2CTransfer(messages, count)
        with self._lock:
            self._ioctl(0x0703, ctypes.c_ulong(address))  # I2C_SLAVE, no FORCE
            result = self._ioctl(0x0707, ctypes.byref(transfer))  # I2C_RDWR
            if result != count:
                raise PeripheralError("Incomplete I2C transaction")
        return bytes(rx)

    def check_address(self, address):
        """Check kernel ownership before changing this device's reset GPIOs."""
        with self._lock:
            self._ioctl(0x0703, ctypes.c_ulong(address))

    def write_reg(self, address, register, payload):
        if isinstance(payload, int):
            payload = bytes([payload])
        return self._transfer(address, int(register).to_bytes(2, "big") + bytes(payload))

    def read_reg(self, address, register, length=1):
        if length < 1:
            raise ValueError("Read length must be positive")
        return self._transfer(address, int(register).to_bytes(2, "big"), length)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class OV5640:
    ADDRESS = 0x3C

    def __init__(self, bus, *, data_dir=None, sleep=time.sleep, timeout=2.0):
        self.bus, self.data_dir, self.sleep = bus, data_dir, sleep
        self.timeout = timeout
        self.initialized = self.af_ready = False

    def _write(self, register, payload):
        for attempt in range(5):
            try:
                return self.bus.write_reg(self.ADDRESS, register, payload)
            except OSError as error:
                if error.errno not in (errno.EAGAIN, errno.EBUSY) or attempt == 4:
                    raise
                self.sleep(0.01)

    def _read(self, register):
        result = self.bus.read_reg(self.ADDRESS, register, 1)
        if len(result) != 1:
            raise PeripheralError("Short OV5640 register read")
        return result[0]

    def _wait(self, register, expected):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self._read(register) == expected:
                return
            self.sleep(0.005)
        raise TimeoutError("OV5640 register 0x{:04x} did not become 0x{:02x}".format(register, expected))

    def initialize(self, *, autofocus=True):
        if getattr(self.bus, "frequency_hz", None) != 40000:
            raise PeripheralError("OV5640 original design requires verified I2C1 clock-frequency = 40000 in device tree")
        registers = json.loads(load_data("ov5640_registers.json", self.data_dir))
        # Read and verify all data before touching the sensor.
        if autofocus:
            load_data("ov5640_af.bin", self.data_dir)
        self.initialized = self.af_ready = False
        self._write(0x3008, 0x82)
        self.sleep(0.01)
        self._write(0x3008, 0x42)
        chip_id = (self._read(0x300A) << 8) | self._read(0x300B)
        if chip_id != 0x5640:
            raise PeripheralError("Unexpected camera ID: 0x{:04x}".format(chip_id))
        for register, value in registers:
            self._write(register, value)
        self._write(0x3008, 0x02)
        self.sleep(0.01)
        self.initialized = True
        if autofocus:
            self.initialize_autofocus()
            self.focus()

    def initialize_autofocus(self):
        if not self.initialized:
            raise PeripheralError("Initialize OV5640 before autofocus")
        if self.af_ready:
            return
        firmware = load_data("ov5640_af.bin", self.data_dir)
        self._write(0x3000, 0x20)
        for offset in range(0, len(firmware), 64):
            self._write(0x8000 + offset, firmware[offset:offset + 64])
        for register in range(0x3022, 0x3029):
            self._write(register, 0)
        self._write(0x3029, 0x7F)
        self._write(0x3000, 0)
        self._wait(0x3029, 0x70)
        self._write(0x3004, self._read(0x3004) | 0x60)
        self._write(0x3001, self._read(0x3001) & ~0x40)
        self._write(0x3005, self._read(0x3005) | 0x40)
        self._write(0x3606, 0x3F)
        self.af_ready = True

    def focus(self):
        if not self.af_ready:
            raise PeripheralError("Autofocus firmware is not ready")
        self._write(0x3022, 1)
        self._write(0x3022, 8)
        self._wait(0x3023, 0)
        self._write(0x3023, 1)
        self._write(0x3022, 3)
        self._wait(0x3023, 0)
        self._wait(0x3029, 0x10)
        self._write(0x3022, 6)

    def release_focus(self):
        if not self.af_ready:
            raise PeripheralError("Autofocus firmware is not ready")
        self._write(0x3022, 8)
        self._wait(0x3029, 0x70)

    def set_light(self, enabled):
        if not self.initialized:
            raise PeripheralError("Camera is not initialized")
        self._write(0x3016, 2)
        self._write(0x301C, 2)
        self._write(0x3019, 2 if enabled else 0)

    def set_test_pattern(self, pattern=0):
        if pattern not in (0, 1, 2):
            raise ValueError("Pattern must be 0 (off), 1 (bars) or 2 (scrolling bars)")
        if not self.initialized:
            raise PeripheralError("Camera is not initialized")
        self._write(0x503D, (0, 0x80, 0x82)[pattern])
        self._write(0x4741, 0)


def make_ps_gpio_factory(hwh_path):
    """Allow only the original GT911 MIO0 and EMIO0/PS54 pin assignments."""
    tree = ET.parse(hwh_path)
    modules = tree.findall(".//MODULE[@MODTYPE='processing_system7']")
    if len(modules) != 1:
        raise PeripheralError("Need one processing_system7 module in HWH")
    parameters = {p.get("NAME"): p.get("VALUE") for p in modules[0].findall("./PARAMETERS/PARAMETER")}
    if parameters.get("PCW_GPIO_EMIO_GPIO_ENABLE") != "1" or parameters.get("PCW_GPIO_EMIO_GPIO_IO") != "1":
        raise PeripheralError("Expected exactly one EMIO GPIO (PS54) in original HWH")
    if parameters.get("PCW_GPIO_MIO_GPIO_ENABLE") != "1" or parameters.get("PCW_MIO_0_DIRECTION") != "inout":
        raise PeripheralError("HWH does not confirm original MIO0 GPIO")
    from pynq import GPIO

    def factory(pin, direction):
        if pin not in (0, 54):
            raise PeripheralError("Pin is not established by original HWH and lcd.h")
        # get_gpio_pin(0) includes the Zynq-7000 offset of 54 MIO pins.
        linux_index = GPIO.get_gpio_pin(0) - 54 + pin
        return GPIO(linux_index, direction)
    return factory


class GT911:
    """Polling touch driver: fresh press/release state, 180-degree coordinates."""
    def __init__(self, bus, gpio_factory, *, data_dir=None, flip=True, sleep=time.sleep):
        self.bus, self.gpio_factory = bus, gpio_factory
        self.data_dir, self.flip, self.sleep = data_dir, flip, sleep
        self.address = 0x5D
        self.points, self.pressed, self.just_pressed = [], False, False
        self.initialized = False
        self._int_pin = self._reset_pin = None

    def initialize(self):
        config = load_data("gt911_config.bin", self.data_dir)
        if len(config) != 184:
            raise PeripheralError("Unexpected GT911 configuration length")
        if hasattr(self.bus, "check_address"):
            self.bus.check_address(self.address)
        # INT low during reset selects 0x5D. Original C drove high while using
        # 0x5D; Linux goodix.c explicitly selects high only for address 0x14.
        self._reset_pin = self.gpio_factory(54, "out")
        self._reset_pin.write(0)
        self._int_pin = self.gpio_factory(0, "out")
        self._int_pin.write(0)
        self.sleep(0.02)
        self._reset_pin.write(1)
        self.sleep(0.006)
        self._int_pin.write(0)
        self.sleep(0.05)
        self._int_pin.release()
        self._int_pin = None
        self._int_pin = self.gpio_factory(0, "in")
        product = self.bus.read_reg(self.address, 0x8140, 4).rstrip(b"\x00")
        if product != b"911":
            raise PeripheralError("Expected GT911 product ID; got " + repr(product))
        self.bus.write_reg(self.address, 0x8040, 2)
        self.bus.write_reg(self.address, 0x8047, config)
        # Fresh flag must be 1. It is not a request to write persistent NVM.
        self.bus.write_reg(self.address, 0x80FF, bytes([(-sum(config)) & 0xFF, 1]))
        self.sleep(0.01)
        self.bus.write_reg(self.address, 0x8040, 0)
        self.initialized = True

    def poll(self):
        if not self.initialized:
            raise PeripheralError("GT911 is not initialized")
        self.just_pressed = False
        status = self.bus.read_reg(self.address, 0x814E, 1)[0]
        if not status & 0x80:
            return self.points
        count = status & 0x0F
        try:
            if count > 5:
                self.points, self.pressed = [], False
                raise PeripheralError("GT911 reported more than the supported five contacts")
            payload = self.bus.read_reg(self.address, 0x814F, count * 8) if count else b""
            if len(payload) != count * 8:
                raise PeripheralError("Incomplete GT911 contact packet")
            points = []
            for i in range(count):
                point = payload[i * 8:(i + 1) * 8]
                x, y = int.from_bytes(point[1:3], "little"), int.from_bytes(point[3:5], "little")
                if not (0 <= x < 800 and 0 <= y < 480):
                    raise PeripheralError("GT911 coordinate exceeds 800x480")
                points.append((799 - x, 479 - y) if self.flip else (x, y))
            self.just_pressed = bool(points) and not self.pressed
            self.points, self.pressed = points, bool(points)
            return points
        except BaseException:
            self.points, self.pressed, self.just_pressed = [], False, False
            raise
        finally:
            self.bus.write_reg(self.address, 0x814E, 0)

    def close(self):
        for name in ("_int_pin", "_reset_pin"):
            pin = getattr(self, name)
            if pin is not None:
                pin.release()
                setattr(self, name, None)
        self.initialized = False


class LCDFrame:
    """Logical 800x480 BGR888 canvas, matching original LCD_DrawPoint rotation."""
    def __init__(self, *, flip=True, data_dir=None):
        self.flip, self.data_dir = flip, data_dir
        self.pixels = np.zeros((480, 800, 3), dtype=np.uint8)

    @staticmethod
    def _bgr(color):
        return [color & 255, (color >> 8) & 255, (color >> 16) & 255]

    def clear(self, color=0):
        self.pixels[:] = self._bgr(color)

    def rectangle(self, x, y, width, height, color):
        if width <= 0 or height <= 0:
            return
        x0, y0, x1, y1 = max(0, x), max(0, y), min(800, x + width), min(480, y + height)
        if x1 > x0 and y1 > y0:
            self.pixels[y0:y1, x0:x1] = self._bgr(color)

    def picture(self, frame_bgr, x=352, y=16, scale=2):
        frame = np.asarray(frame_bgr)
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or scale < 1 or int(scale) != scale:
            raise ValueError("Expected HxWx3 uint8 BGR888 and a positive integer scale")
        scale = int(scale)
        expanded = np.repeat(np.repeat(frame, scale, axis=0), scale, axis=1)
        h, w = expanded.shape[:2]
        x0, y0, x1, y1 = max(0, x), max(0, y), min(800, x + w), min(480, y + h)
        if x1 > x0 and y1 > y0:
            self.pixels[y0:y1, x0:x1] = expanded[y0 - y:y1 - y, x0 - x:x1 - x]

    def text(self, x, y, text, *, font=32, color=0x00FF00, background=0):
        if font not in (12, 16, 24, 32):
            raise ValueError("Font must be 12, 16, 24 or 32")
        glyphs = load_data("font{}.bin".format(font), self.data_dir)
        width, groups, origin_x = font // 2, (font + 7) // 8, x
        for char in text:
            if char == "\n":
                x, y = origin_x, y + font
                continue
            if not 32 <= ord(char) <= 126:
                raise ValueError("Original font supports ASCII characters 32..126")
            self.rectangle(x, y, width, font, background)
            start = (ord(char) - 32) * width * groups
            for dx in range(width):
                for dy in range(font):
                    if glyphs[start + dx * groups + dy // 8] & (0x80 >> (dy % 8)):
                        if 0 <= x + dx < 800 and 0 <= y + dy < 480:
                            self.pixels[y + dy, x + dx] = self._bgr(color)
            x += width

    def physical_frame(self):
        return np.ascontiguousarray(self.pixels[::-1, ::-1] if self.flip else self.pixels)


class VideoDMA:
    """Direct-register, single-frame-store driver for the exact original VDMA.

    Each capture runs for one whole frame and halts before invalidate/copy.
    This avoids copying a frame while S2MM is changing it. Display and capture
    channels are reset and stopped separately; neither resets the other one.
    """
    ERROR_MASK = 0xFF0

    def __init__(self, mmio, parameters, *, allocator=None, timeout=2.0):
        p = {str(k).lower(): v for k, v in parameters.items()}
        required = {"c_include_sg": 0, "c_num_fstores": 1,
            "c_include_mm2s": 1, "c_include_s2mm": 1,
            "c_m_axis_mm2s_tdata_width": 24, "c_s_axis_s2mm_tdata_width": 24,
            "c_addr_width": 32}
        for key, expected in required.items():
            try:
                actual = int(str(p[key]), 0)
            except (KeyError, ValueError):
                raise PeripheralError("Missing/invalid VDMA parameter " + key)
            if actual != expected:
                raise PeripheralError("Unsupported VDMA {} = {}; expected {}".format(key, actual, expected))
        self.mmio, self.timeout = mmio, timeout
        if allocator is None:
            from pynq import allocate
            allocator = allocate
        self.allocator = allocator
        self.capture_buffer = self.display_buffer = None

    def _wait(self, predicate, message):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.001)
        raise TimeoutError(message)

    def _stop(self, channel):
        try:
            self.mmio.write(channel, self.mmio.read(channel) & ~1)
            self._wait(lambda: bool(self.mmio.read(channel + 4) & 1), "VDMA did not halt; buffers retained")
        except BaseException:
            if not any(item is self for item in _FAULTED_VIDEO):
                _FAULTED_VIDEO.append(self)
            raise

    def _reset(self, channel):
        try:
            self.mmio.write(channel, 4)
            self._wait(lambda: not self.mmio.read(channel) & 4, "VDMA channel reset timed out")
        except BaseException:
            if not any(item is self for item in _FAULTED_VIDEO):
                _FAULTED_VIDEO.append(self)
            raise

    def _allocate(self, shape):
        buffer = self.allocator(shape=shape, dtype=np.uint8)
        address = int(buffer.physical_address)
        # Original VDMA HP1/HP2 address segments cover only 0..0x1fffffff.
        # PYNQ CMA may otherwise allocate from the upper half of the 1 GiB RAM.
        if address % 8 or address <= 0 or address + buffer.nbytes > 0x20000000:
            buffer.freebuffer()
            raise PeripheralError("VDMA requires an 8-byte aligned CMA allocation wholly below 0x20000000 (512 MiB)")
        buffer[:] = 0
        buffer.flush()
        return buffer

    def start_capture(self):
        """Allocate/reset the 224x224 BGR capture; read_frame triggers capture."""
        if self.capture_buffer is None:
            self._reset(0x30)
            self.capture_buffer = self._allocate((224, 224, 3))
            if not any(item is self for item in _ACTIVE_VIDEO):
                _ACTIVE_VIDEO.append(self)

    def read_frame(self):
        self.start_capture()
        for attempt in range(2):
            try:
                return self._capture_once()
            except PeripheralError:
                if attempt:
                    raise
                # The first frame after the sensor wakes can be malformed;
                # halt, reset and try once more before reporting a fault.
                self._stop(0x30)
                time.sleep(0.02)
            except BaseException:
                # Preserve the allocation even if the halt fails: hardware may
                # still own it.
                self._stop(0x30)
                raise

    def _capture_once(self):
        self._reset(0x30)
        self.mmio.write(0x34, 0x7000 | self.ERROR_MASK)
        self.mmio.write(0xA4, 224 * 3)   # HSize
        self.mmio.write(0xA8, 224 * 3)   # Stride (frame delay stays 0)
        self.mmio.write(0xAC, int(self.capture_buffer.physical_address))
        # Genlock only. The design has a single frame store, so enabling the
        # circular/tail-pointer bit (0x2) makes the DMA wrap and report
        # FSize-More instead of ever writing a frame.
        self.mmio.write(0x30, 0x08)
        self.mmio.write(0x30, self.mmio.read(0x30) | 0x1)   # run
        self.mmio.write(0xA0, 224)  # VSIZE last starts the transfer.
        def complete():
            status = self.mmio.read(0x34)
            if status & self.ERROR_MASK:
                raise PeripheralError("Camera VDMA status 0x{:08x}".format(status))
            return bool(status & 0x1000)
        self._wait(complete, "No complete camera frame before timeout")
        self._stop(0x30)
        self.capture_buffer.invalidate()
        return np.array(self.capture_buffer, copy=True)

    def start_display(self, vtc_mmio):
        if self.display_buffer is None:
            self._reset(0x00)
            self.display_buffer = self._allocate((480, 800, 3))
            if not any(item is self for item in _ACTIVE_VIDEO):
                _ACTIVE_VIDEO.append(self)
        try:
            self.mmio.write(0x04, 0x7000 | self.ERROR_MASK)
            self.mmio.write(0x5C, int(self.display_buffer.physical_address))
            self.mmio.write(0x58, 800 * 3)
            self.mmio.write(0x54, 800 * 3)
            self.mmio.write(0x00, 0x10003)
            self.mmio.write(0x50, 480)
            # Preserve HWH's static 800x480 timing, like the original driver.
            vtc_mmio.write(0, vtc_mmio.read(0) | 0x07)
        except BaseException:
            self._stop(0x00)
            raise

    def write_display(self, frame_bgr):
        if self.display_buffer is None:
            raise PeripheralError("Display is not started")
        frame = np.asarray(frame_bgr)
        if frame.shape != (480, 800, 3) or frame.dtype != np.uint8:
            raise ValueError("LCD expects (480,800,3) uint8 physical BGR888")
        status = self.mmio.read(0x04)
        if status & self.ERROR_MASK:
            raise PeripheralError("LCD VDMA status 0x{:08x}".format(status))
        self.display_buffer[:] = frame
        self.display_buffer.flush()

    def close(self):
        # Never free an active DMA target on a timeout/error.
        for channel, name in ((0x30, "capture_buffer"), (0x00, "display_buffer")):
            buffer = getattr(self, name)
            if buffer is not None:
                self._stop(channel)
                buffer.freebuffer()
                setattr(self, name, None)
        _FAULTED_VIDEO[:] = [item for item in _FAULTED_VIDEO if item is not self]
        _ACTIVE_VIDEO[:] = [item for item in _ACTIVE_VIDEO if item is not self]
