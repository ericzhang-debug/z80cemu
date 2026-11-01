import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.mc6850 import MC6850

class ACIARegisterTests(unittest.TestCase):
    def make(self):
        a = MC6850(0x30, 10000, 1000)
        a.write_port(0x30, 0x14)
        return a

    def test_transmit_double_buffer_and_interrupt(self):
        a = self.make(); a.write_port(0x30, 0x34)
        self.assertTrue(a.irq_active())
        a.write_port(0x31, ord('A'))
        self.assertFalse(a.irq_active())
        a.tick(10)
        self.assertTrue(a.irq_active())
        a.write_port(0x31, ord('B'))
        a.tick(99); self.assertEqual(bytes(a.output), b'')
        a.tick(1); self.assertEqual(bytes(a.output), b'A')
        self.assertTrue(a.irq_active())
        a.tick(100); self.assertEqual(bytes(a.output), b'AB')

    def test_cts_masks_tdre_and_defers_start(self):
        a = self.make(); a.set_modem_inputs(cts=1)
        self.assertEqual(a.status() & 0x0a, 8)
        a.write_port(0x31, 0x35); a.tick(500)
        self.assertEqual(bytes(a.output), b'')
        a.set_modem_inputs(cts=0); a.tick(110)
        self.assertEqual(bytes(a.output), b'5')

    def test_dcd_status_latch_and_interrupt_clear_sequence(self):
        a = self.make(); a.write_port(0x30, 0x94)
        a.set_modem_inputs(dcd=1); a.set_modem_inputs(dcd=0)
        self.assertTrue(a.irq_active())
        self.assertEqual(a.read_port(0x30) & 0x84, 0x84)
        a.read_port(0x31)
        self.assertFalse(a.irq_active())
        self.assertEqual(a.status() & 4, 0)

    def test_error_bits_follow_received_character(self):
        a = self.make(); a.receive_byte(0xa5, framing_error=True, parity_error=True)
        a.tick(100); self.assertEqual(a.read_port(0x30) & 0x51, 0x51)
        self.assertEqual(a.read_port(0x31), 0xa5)
        self.assertEqual(a.status() & 0x51, 0)

    def test_word_formats_and_rts(self):
        a = self.make(); a.write_port(0x30, 0x40)
        self.assertEqual(a.rts, 1)
        a.receive_byte(0xfe); a.tick(a.frame_cycles())
        self.assertEqual(a.read_port(0x31), 0x7e)
        a.write_port(0x30, 0x60); self.assertTrue(a.break_active)

    def test_chunk_independent_tx(self):
        a, b = self.make(), self.make()
        for device in (a, b): device.write_port(0x31, ord('X'))
        a.tick(110)
        for _ in range(110): b.tick(1)
        self.assertEqual(bytes(a.output), bytes(b.output))

if __name__ == '__main__': unittest.main()
