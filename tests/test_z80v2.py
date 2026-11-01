import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boards.z80v2 import Z80V2

class BoardTests(unittest.TestCase):
    def test_memory_switch_preserves_both_chips(self):
        b = Z80V2(); b.rom.load(b'\x42'); b.ram.write(0, 0x99)
        self.assertEqual(b.read(0), 0x42)
        b.write(0, 1); self.assertEqual(b.ram.read(0), 0x99)
        b.io_write(0x7f01, 0); self.assertEqual(b.read(0), 0x99)
        b.write(0, 0x77); b.io_write(0x7f00, 0)
        self.assertEqual(b.read(0), 0x42)
        b.io_write(1, 0); self.assertEqual(b.read(0), 0x77)
        b.reset(); self.assertEqual(b.read(0), 0x42)
        self.assertEqual(b.ram.read(0), 0x77)

    def test_cpu_led_and_serial_ports(self):
        b = Z80V2()
        b.rom.load(bytes.fromhex('3e a5 d3 02 3e 14 d3 3e 3e 5a d3 3f 76'))
        for _ in range(7): b.step()
        self.assertEqual(b.ports[2].value, 0xa5)
        self.assertEqual(b.ports[0x3e].control, 0x14)
        self.assertEqual(b.ports[0x3e].tx, 0x5a)

    def test_serial_mirror_and_unmapped(self):
        b = Z80V2(); self.assertIs(b.ports[0x123e], b.ports[0x3e])
        self.assertEqual(b.io_read(0x80), 0xff)
