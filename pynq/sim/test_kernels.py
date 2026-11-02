import unittest
import numpy as np
from trash_pynq.kernels import Kernels, KernelTimeout


class Buffer(np.ndarray):
    def __new__(cls, size, address=0x1000000):
        obj = np.zeros(size, dtype=np.int16).view(cls)
        obj.device_address = address
        obj.events = []
        return obj

    def flush(self):
        self.events.append('flush')

    def invalidate(self):
        self.events.append('invalidate')


class IP:
    def __init__(self, done=True):
        self.writes = []
        self.started = False
        self.done = done

    def write(self, offset, value):
        self.writes.append((offset, value))
        if offset == 0:
            self.started = True

    def read(self, offset):
        return 2 if self.started and self.done else 4


class Overlay:
    def __init__(self):
        for name in ['conv', 'pwdwconv', 'fc', 'shortcut']:
            setattr(self, name + '_0', IP())


class KernelTests(unittest.TestCase):
    def test_pw_and_dw_match_bsp_register_writes(self):
        ol = Overlay()
        k = Kernels(ol)
        a, w, b, o = [Buffer(n, 0x1000000 + i*0x100000)
                      for i, n in enumerate([16*112*112, 16*96, 96, 96*112*112])]
        k.pw(a, w, b, o, 16, 96, 1, 112)
        self.assertEqual(ol.pwdwconv_0.writes,
                         [(0x10,a.device_address),(0x18,w.device_address),(0x20,w.device_address),
                          (0x28,o.device_address),(0x30,b.device_address),(0x38,b.device_address),
                          (0x40,16),(0x48,96),(0x50,1),(0x58,112),(0x60,1),(0x68,1),(0,1)])
        self.assertEqual(o.events, ['flush', 'invalidate'])
        # Kernels resolves its four IP handles once at construction because PYNQ
        # rebuilds a DefaultIP on every attribute access; swap the mock first.
        ol.pwdwconv_0 = IP()
        k = Kernels(ol)
        a = Buffer(96*112*112)
        w = Buffer(96*9, 0x2000000)
        k.dw(a,w,b,o,96,112,2)
        writes = dict(ol.pwdwconv_0.writes)
        self.assertEqual(writes[0x20], o.device_address)
        self.assertEqual(writes[0x30], w.device_address)
        self.assertEqual(writes[0x50], 2)
        self.assertEqual(writes[0x68], 0)

    def test_conv_fc_shortcut_and_cache_sync(self):
        ol = Overlay()
        k = Kernels(ol)
        a,w,b,o = Buffer(150528),Buffer(864,0x2000000),Buffer(32,0x3000000),Buffer(401408,0x4000000)
        k.conv(a,w,b,o)
        self.assertEqual(dict(ol.conv_0.writes)[0x38],o.device_address)
        self.assertIn('flush',a.events)
        k.fc(Buffer(62720),Buffer(7680),Buffer(6),Buffer(6))
        k.shortcut(Buffer(24*56*56), Buffer(24*56*56), Buffer(24*56*56), 24*56*56)
        self.assertEqual(len(k.trace), 3)

    def test_reject_virtual_unaligned_outside_window_and_small(self):
        k=Kernels(Overlay())
        for buf in [np.zeros(16,dtype=np.int16),Buffer(16,0x1000001),Buffer(16,0x40000000)]:
            with self.assertRaises((TypeError,ValueError)):
                k.address(buf)
        with self.assertRaises(ValueError):
            k.fc(Buffer(1),Buffer(1),Buffer(1),Buffer(1))

    def test_timeout_faults_and_pins_buffers(self):
        ol = Overlay()
        ol.shortcut_0=IP(done=False)
        k=Kernels(ol, timeout=0.001)
        buffers=[Buffer(16) for _ in range(3)]
        with self.assertRaises(KernelTimeout):
            k.shortcut(*buffers,16)
        self.assertTrue(k.faulted)
        self.assertEqual(len(k._pinned),3)
        self.assertNotIn('invalidate',buffers[-1].events)
        with self.assertRaises(RuntimeError):
            k.shortcut(*buffers,16)


if __name__=='__main__':
    unittest.main()
