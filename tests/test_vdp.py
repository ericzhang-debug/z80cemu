import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.tms9918a import TMS9918A

class VDPTests(unittest.TestCase):
    def setUp(self): self.v = TMS9918A(cpu_hz=6000)
    def reg(self, index, value):
        self.v.write_port(0xbf, value); self.v.write_port(0xbf, 0x80 | index)
    def address(self, addr, write=False):
        self.v.write_port(0xbf, addr & 255)
        self.v.write_port(0xbf, ((addr >> 8) & 63) | (0x40 if write else 0))
    def test_write_read_wrap_and_prefetch(self):
        self.address(0x3fff, True)
        self.v.write_port(0xbe, 0x12); self.v.write_port(0xbe, 0x34)
        self.assertEqual(self.v.vram[0x3fff], 0x12)
        self.assertEqual(self.v.vram[0], 0x34)
        self.address(0x3fff)
        self.assertEqual([self.v.read_port(0xbe), self.v.read_port(0xbe)], [0x12, 0x34])
    def test_status_read_clears_irq_and_control_latch(self):
        self.reg(1, 0x20); self.v.tick(100)
        self.assertTrue(self.v.irq_active())
        self.v.write_port(0xbf, 0x45)
        self.assertTrue(self.v.read_port(0xbf) & 0x80)
        self.assertFalse(self.v.irq_active())
        self.v.write_port(0xbf, 0xaa)
        self.assertEqual(self.v.control_latch, 0xaa)
    def test_frame_accumulator(self):
        self.v.tick(99); self.assertEqual(self.v.frame_number, 0)
        self.v.tick(201); self.assertEqual(self.v.frame_number, 3)
    def test_blanked_display(self):
        self.reg(7, 0xf4)
        self.assertEqual(set(self.v.render()), {4})
    def test_text_mode(self):
        self.reg(1, 0x50); self.reg(2, 0); self.reg(4, 1); self.reg(7, 0xf4)
        self.v.vram[0] = 1; self.v.vram[0x808] = 0xa0
        image = self.v.render()
        self.assertEqual(list(image[8:14]), [15, 4, 15, 4, 4, 4])
        self.assertEqual(image[0], 4)
    def test_graphics_i(self):
        self.reg(1, 0x40); self.reg(2, 0); self.reg(3, 0x20); self.reg(4, 1)
        self.reg(5, 0x30); self.v.vram[0x1800] = 0xd0
        self.v.vram[0] = 2; self.v.vram[0x810] = 0x80; self.v.vram[0x800] = 0xa2
        image = self.v.render()
        self.assertEqual(list(image[:2]), [10, 2])
    def test_graphics_ii_block_and_color(self):
        self.reg(0, 2); self.reg(1, 0x40); self.reg(2, 0x0e); self.reg(3, 0xff); self.reg(4, 3)
        self.reg(5, 0x30); self.v.vram[0x1800] = 0xd0
        self.v.vram[0x3800 + 256] = 3
        self.v.vram[0x800 + 24] = 0x80; self.v.vram[0x2800 + 24] = 0xc2
        image = self.v.render()
        self.assertEqual(list(image[64*256:64*256+2]), [12, 2])
    def test_multicolor_quadrants(self):
        self.reg(1, 0x48); self.reg(2, 0); self.reg(4, 1)
        self.reg(5, 0x30); self.v.vram[0x1800] = 0xd0
        self.v.vram[0] = 1; self.v.vram[0x808] = 0x23; self.v.vram[0x809] = 0x45
        image = self.v.render()
        self.assertEqual([image[0], image[4], image[4*256], image[4*256+4]], [2,3,4,5])
    def test_sprite_priority_collision_overflow(self):
        self.reg(1, 0x40); self.reg(5, 0x30); self.reg(6, 4)
        for i in range(5): self.v.vram[0x1800+i*4:0x1804+i*4] = bytes([0xff, 0, 0, 2+i])
        self.v.vram[0x1814] = 0xd0
        self.v.vram[0x2000] = 0x80
        self.v.tick(100)
        self.assertEqual(self.v.status & 0x7f, 0x64)
        self.assertEqual(self.v.render()[0], 2)
        self.assertEqual(self.v.read_port(0xbf) & 0x7f, 0x64)
        self.assertEqual(self.v.status, 0x1f)
    def test_transparent_sprite_does_not_hide_lower_sprite(self):
        self.reg(1, 0x40); self.reg(5, 0x30); self.reg(6, 4)
        self.v.vram[0x1800:0x1809] = bytes([0xff, 0, 0, 0, 0xff, 0, 0, 7, 0xd0])
        self.v.vram[0x2000] = 0x80
        self.assertEqual(self.v.render()[0], 7)
        self.v.tick(100)
        self.assertTrue(self.v.status & 0x20)

if __name__ == '__main__': unittest.main()
