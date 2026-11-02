"""Host tests for protocol, image coordinates and DMA ownership; no device I/O."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trash_pynq import peripherals as p


PARAMETERS = {"C_INCLUDE_SG": "0", "C_NUM_FSTORES": "1", "C_INCLUDE_MM2S": "1",
              "C_INCLUDE_S2MM": "1", "C_M_AXIS_MM2S_TDATA_WIDTH": "24",
              "C_S_AXIS_S2MM_TDATA_WIDTH": "24", "c_addr_width": "32"}


class Buffer(np.ndarray):
    def __new__(cls, shape, address):
        obj = np.zeros(shape, np.uint8).view(cls)
        obj.physical_address = address
        obj.flushed, obj.invalidated, obj.freed = 0, 0, False
        return obj

    def flush(self):
        self.flushed += 1

    def invalidate(self):
        self.invalidated += 1

    def freebuffer(self):
        self.freed = True


class MMIO:
    def __init__(self):
        self.regs = {0x00: 0, 0x04: 1, 0x30: 0, 0x34: 1}
        self.writes = []
        self.complete, self.stuck, self.error = True, False, 0

    def read(self, address):
        return self.regs.get(address, 0)

    def write(self, address, value):
        self.writes.append((address, value))
        if address in (0, 0x30):
            if value & 4:
                self.regs[address], self.regs[address + 4] = 0, 1
            else:
                self.regs[address] = value
                self.regs[address + 4] = 0 if value & 1 or self.stuck else 1
        elif address in (4, 0x34):
            self.regs[address] = self.regs.get(address, 0) & ~value
        elif address == 0xA0:
            self.regs[address] = value
            if self.complete:
                self.regs[0x34] = self.error or 0x1001
        else:
            self.regs[address] = value


class Bus:
    frequency_hz = 40000

    def __init__(self):
        self.registers = {0x300A: b"\x56", 0x300B: b"\x40", 0x3004: b"\x00",
                          0x3001: b"\xff", 0x3005: b"\x00", 0x3029: b"\x70",
                          0x3023: b"\x00", 0x8140: b"911\x00"}
        self.writes = []

    def read_reg(self, address, register, length=1):
        return self.registers.get(register, b"\x00" * length)[:length]

    def write_reg(self, address, register, payload):
        data = bytes([payload]) if isinstance(payload, int) else bytes(payload)
        self.writes.append((address, register, data))
        self.registers[register] = data
        if register == 0x3000 and data == b"\x00":
            self.registers[0x3029] = b"\x70"
        if register == 0x3022 and data == b"\x03":
            self.registers[0x3023], self.registers[0x3029] = b"\x00", b"\x10"
        if register == 0x3022 and data == b"\x08":
            self.registers[0x3023], self.registers[0x3029] = b"\x00", b"\x70"


class Pin:
    def __init__(self, number, direction, log):
        self.number, self.direction, self.log = number, direction, log
        self.log.append((number, direction))

    def write(self, value):
        self.log.append((self.number, value))

    def release(self):
        self.log.append((self.number, "release"))


class PeripheralTests(unittest.TestCase):
    def tearDown(self):
        p._FAULTED_VIDEO.clear()
        p._ACTIVE_VIDEO.clear()

    def test_original_data_extracts_byte_for_byte(self):
        path = ROOT / "data/peripherals/extract_from_vitis.py"
        spec = importlib.util.spec_from_file_location("extract_peripherals", path)
        extractor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extractor)
        source = ROOT.parent / "original/vitis_trash/Trash_LCD_OV5640/Lib"
        if not source.exists():
            self.skipTest("Original source is not present in deployed package")
        with tempfile.TemporaryDirectory(dir=str(ROOT / "sim")) as folder:
            self.assertIn(ROOT.resolve(), Path(folder).resolve().parents)
            manifest = extractor.extract(source, Path(folder))
            for name in manifest["files"]:
                self.assertEqual((Path(folder) / name).read_bytes(), p.load_data(name))
        registers = json.loads(p.load_data("ov5640_registers.json"))
        self.assertEqual(len(registers), 255)
        self.assertEqual(dict(registers)[0x4300], 0x6F)
        self.assertEqual(dict(registers)[0x3809], 224)

    def test_camera_af_transfer_id_and_light(self):
        bus = Bus()
        camera = p.OV5640(bus, sleep=lambda _: None)
        camera.initialize()
        firmware_writes = [(reg, data) for _, reg, data in bus.writes if reg >= 0x8000]
        self.assertEqual(b"".join(data for _, data in firmware_writes), p.load_data("ov5640_af.bin"))
        self.assertEqual(firmware_writes[0][0], 0x8000)
        self.assertTrue(camera.af_ready)
        camera.set_light(True)
        self.assertEqual(bus.writes[-1], (0x3C, 0x3019, b"\x02"))
        camera.set_light(False)
        self.assertEqual(bus.writes[-1], (0x3C, 0x3019, b"\x00"))
        camera.release_focus()

    def test_camera_wrong_id_and_unknown_clock_fail(self):
        bus = Bus()
        bus.frequency_hz = None
        with self.assertRaises(p.PeripheralError):
            p.OV5640(bus).initialize()
        self.assertEqual(bus.writes, [])
        bus.frequency_hz = 40000
        bus.registers[0x300B] = b"\x41"
        with self.assertRaises(p.PeripheralError):
            p.OV5640(bus, sleep=lambda _: None).initialize()
        self.assertFalse(any(reg == 0x4300 for _, reg, _ in bus.writes))

    def test_discovery_matches_ps_address_and_frequency(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / "sim")) as folder:
            self.assertIn(ROOT.resolve(), Path(folder).resolve().parents)
            node = Path(folder) / "i2c-7/device/of_node"
            node.mkdir(parents=True)
            (node / "reg").write_bytes(bytes.fromhex("e000500000001000"))
            (node / "clock-frequency").write_bytes((40000).to_bytes(4, "big"))
            self.assertEqual(p.discover_ps_i2c(1, folder), (7, 40000))
            with self.assertRaises(p.PeripheralError):
                p.discover_ps_i2c(0, folder)

    def test_linux_i2c_combined_transaction_structure(self):
        bus = p.LinuxI2C.__new__(p.LinuxI2C)
        bus._fd, bus._lock = 9, threading.RLock()
        calls = []

        class Libc:
            def ioctl(self, fd, request, argument):
                calls.append(request.value)
                if request.value == 0x0703:
                    return 0
                transfer = ctypes.cast(argument, ctypes.POINTER(p._I2CTransfer)).contents
                self_outer.assertEqual(transfer.nmsgs, 2)
                self_outer.assertEqual(transfer.msgs[0].addr, 0x3C)
                self_outer.assertEqual(bytes(transfer.msgs[0].buf[:2]), b"\x30\x0a")
                self_outer.assertEqual(transfer.msgs[1].flags, 1)
                transfer.msgs[1].buf[0] = 0x56
                return 2
        self_outer = self
        bus._libc = Libc()
        self.assertEqual(bus.read_reg(0x3C, 0x300A), b"\x56")
        self.assertEqual(calls, [0x0703, 0x0707])

    def test_touch_reset_address_press_release_and_flip(self):
        log, bus = [], Bus()
        touch = p.GT911(bus, lambda pin, direction: Pin(pin, direction, log), sleep=lambda _: None)
        touch.initialize()
        self.assertLess(log.index((0, 0)), log.index((54, 1)))
        config = p.load_data("gt911_config.bin")
        self.assertIn((0x5D, 0x80FF, bytes([(-sum(config)) & 255, 1])), bus.writes)
        bus.registers[0x814E] = b"\x81"
        bus.registers[0x814F] = bytes([0, 100, 0, 200, 0, 1, 0, 0])
        self.assertEqual(touch.poll(), [(699, 279)])
        self.assertTrue(touch.just_pressed)
        bus.registers[0x814E] = b"\x80"
        self.assertEqual(touch.poll(), [])
        self.assertFalse(touch.pressed)
        self.assertFalse(touch.just_pressed)

    def test_gpio_factory_maps_only_mio0_and_emio0(self):
        values = {"PCW_GPIO_EMIO_GPIO_ENABLE": "1", "PCW_GPIO_EMIO_GPIO_IO": "1",
                  "PCW_GPIO_MIO_GPIO_ENABLE": "1", "PCW_MIO_0_DIRECTION": "inout"}
        parameters = "".join('<PARAMETER NAME="{}" VALUE="{}"/>'.format(k, v) for k, v in values.items())
        hwh = '<EDKSYSTEM><MODULES><MODULE MODTYPE="processing_system7"><PARAMETERS>' + parameters + '</PARAMETERS></MODULE></MODULES></EDKSYSTEM>'
        class GPIO:
            @staticmethod
            def get_gpio_pin(index):
                return 154 + index
            def __init__(self, index, direction):
                self.index, self.direction = index, direction
        with tempfile.TemporaryDirectory(dir=str(ROOT / "sim")) as folder:
            self.assertIn(ROOT.resolve(), Path(folder).resolve().parents)
            path = Path(folder) / "test.hwh"
            path.write_text(hwh)
            with patch.dict(sys.modules, {"pynq": types.SimpleNamespace(GPIO=GPIO)}):
                factory = p.make_ps_gpio_factory(path)
                self.assertEqual(factory(0, "in").index, 100)
                self.assertEqual(factory(54, "out").index, 154)
                with self.assertRaises(p.PeripheralError):
                    factory(55, "out")

    def test_touch_bad_count_acknowledged_and_state_cleared(self):
        bus = Bus()
        touch = p.GT911(bus, None)
        touch.initialized, touch.pressed = True, True
        touch.points = [(1, 2)]
        bus.registers[0x814E] = b"\x86"
        with self.assertRaises(p.PeripheralError):
            touch.poll()
        self.assertFalse(touch.pressed)
        self.assertEqual(bus.writes[-1], (0x5D, 0x814E, b"\x00"))

    def test_lcd_bgr_and_rotation_and_fonts(self):
        canvas = p.LCDFrame()
        canvas.rectangle(-10, 0, 1, 1, 0xFFFFFF)
        self.assertFalse(canvas.pixels.any())
        canvas.rectangle(0, 0, 1, 1, 0x123456)
        self.assertEqual(canvas.physical_frame()[479, 799].tolist(), [0x56, 0x34, 0x12])
        canvas.picture(np.array([[[1, 2, 3]]], np.uint8), x=2, y=3, scale=2)
        np.testing.assert_array_equal(canvas.pixels[3:5, 2:4], np.tile([1, 2, 3], (2, 2, 1)))
        canvas.text(0, 32, "Leaf 123", font=32)
        self.assertTrue(canvas.pixels[32:64, :128].any())

    def test_vdma_snapshot_and_independent_channels(self):
        mmio, allocations = MMIO(), []
        def allocator(shape, dtype):
            buffer = Buffer(shape, 0x18000000 + len(allocations) * 0x200000)
            allocations.append(buffer)
            return buffer
        video = p.VideoDMA(mmio, PARAMETERS, allocator=allocator)
        video.start_display(MMIO())
        before = len(mmio.writes)
        frame = video.read_frame()
        self.assertEqual(frame.shape, (224, 224, 3))
        self.assertEqual(video.capture_buffer.invalidated, 1)
        self.assertFalse(any(reg == 0 for reg, _ in mmio.writes[before:]))
        self.assertEqual(dict(mmio.writes)[0xAC], allocations[1].physical_address)
        self.assertIn((0xA0, 224), mmio.writes)
        self.assertFalse(np.shares_memory(frame, video.capture_buffer))
        video.close()
        self.assertTrue(all(buffer.freed for buffer in allocations))
        self.assertNotIn(video, p._ACTIVE_VIDEO)

    def test_vdma_rejects_upper_cma_window(self):
        allocation = Buffer((224, 224, 3), 0x20000000 - 8)
        video = p.VideoDMA(MMIO(), PARAMETERS, allocator=lambda **kw: allocation)
        with self.assertRaises(p.PeripheralError):
            video.start_capture()
        self.assertTrue(allocation.freed)

    def test_dma_halt_timeout_retains_target_globally(self):
        mmio = MMIO()
        allocation = Buffer((224, 224, 3), 0x18000000)
        video = p.VideoDMA(mmio, PARAMETERS, allocator=lambda **kw: allocation, timeout=0.003)
        video.start_capture()
        mmio.complete, mmio.stuck = False, True
        with self.assertRaises(TimeoutError):
            video.read_frame()
        self.assertIs(p._FAULTED_VIDEO[-1], video)
        self.assertFalse(allocation.freed)
        with self.assertRaises(TimeoutError):
            video.close()
        self.assertFalse(allocation.freed)
        mmio.stuck = False
        video.close()
        self.assertTrue(allocation.freed)

    def test_wrong_vdma_configuration_fails_before_io(self):
        wrong = dict(PARAMETERS, C_NUM_FSTORES="3")
        mmio = MMIO()
        with self.assertRaises(p.PeripheralError):
            p.VideoDMA(mmio, wrong)
        self.assertEqual(mmio.writes, [])


if __name__ == "__main__":
    unittest.main()
