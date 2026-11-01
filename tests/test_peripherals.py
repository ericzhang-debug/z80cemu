import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.mc6850 import MC6850
from components.extends.compact_flash import CompactFlash

class AciaTests(unittest.TestCase):
    def test_transmit_timing_and_reset(self):
        a = MC6850(0x18, 10000, 1000)
        a.write_port(0x18, 0x14)  # 8N1
        a.write_port(0x19, 65)
        self.assertEqual(a.status() & 2, 0)
        a.tick(9); self.assertEqual(list(a.output), [])
        self.assertEqual(a.status() & 2, 0)
        a.tick(1); self.assertEqual(a.status() & 2, 2)
        a.tick(100); self.assertEqual(bytes(a.output), b'A')
        self.assertEqual(a.status() & 2, 2)
        a.write_port(0x18, 3); self.assertEqual(a.status(), 2)

    def test_receive_interrupt_overrun(self):
        a = MC6850(0, 10000, 1000); a.write_port(0, 0x94)
        a.send(b'AB'); a.tick(200)
        self.assertEqual(a.status() & 0xa1, 0x81)
        self.assertEqual(a.read_port(1), ord('A'))
        self.assertEqual(a.read_port(0) & 0xa1, 0xa1)
        a.read_port(1)
        self.assertEqual(a.status() & 0xa1, 0)

    def test_tx_interrupt(self):
        a = MC6850(0); a.write_port(0, 0x20)
        self.assertTrue(a.irq_active()); a.write_port(1, 1)
        self.assertFalse(a.irq_active())

class CFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'disk.img'
        self.path.write_bytes(bytes(2048))
        self.cf = CompactFlash(0x20, self.path)
    def tearDown(self): self.temp.cleanup()
    def setup_lba(self, lba, count=1):
        for reg, value in ((2,count), (3,lba & 255), (4,lba >> 8 & 255), (5,lba >> 16 & 255), (6,0xe0 | (lba >> 24 & 15))):
            self.cf.write_port(0x20 + reg, value)
    def test_two_sector_write_read(self):
        data = bytes(range(256)) * 4
        self.setup_lba(1, 2); self.cf.write_port(0x27, 0x30)
        self.assertEqual(self.cf.read_port(0x27), 0x48)
        for b in data: self.cf.write_port(0x20, b)
        self.assertEqual(self.cf.read_port(0x27), 0x40)
        self.assertEqual(self.path.read_bytes()[512:1536], data)
        self.setup_lba(1, 2); self.cf.write_port(0x27, 0x20)
        self.assertEqual(bytes(self.cf.read_port(0x20) for _ in data), data)
    def test_out_of_range_and_unsupported(self):
        self.setup_lba(4); self.cf.write_port(0x27, 0x20)
        self.assertEqual(self.cf.read_port(0x27), 0x41)
        self.assertEqual(self.cf.read_port(0x21), 0x10)
        self.cf.write_port(0x27, 0xff)
        self.assertEqual(self.cf.read_port(0x21), 4)
    def test_readonly_rejects_write(self):
        self.cf = CompactFlash(0x20, self.path, readonly=True)
        self.setup_lba(0); self.cf.write_port(0x27, 0x30)
        self.assertEqual(self.cf.read_port(0x27), 0x41)
        self.assertEqual(self.path.read_bytes(), bytes(2048))
    def test_incomplete_write_does_not_change_image(self):
        self.setup_lba(0); self.cf.write_port(0x27, 0x30)
        for _ in range(511): self.cf.write_port(0x20, 0xaa)
        self.cf.reset(); self.assertEqual(self.path.read_bytes(), bytes(2048))
    def test_invalid_image_size(self):
        self.path.write_bytes(b'x')
        with self.assertRaises(ValueError): CompactFlash(0, self.path)
    def test_identify_capacity_and_flush(self):
        self.cf.write_port(0x27, 0xec)
        info = bytes(self.cf.read_port(0x20) for _ in range(512))
        self.assertEqual(int.from_bytes(info[120:124], 'little'), 4)
        self.assertEqual(self.cf.read_port(0x27), 0x40)
        self.cf.write_port(0x27, 0xe7)
        self.assertEqual(self.cf.read_port(0x27), 0x40)

if __name__ == '__main__': unittest.main()
