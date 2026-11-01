"""End-to-end execution of the original TPBUG monitor on platform components."""
import sys
import unittest
from unittest.mock import Mock
from unittest.mock import patch
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines.tp801 import build

def run_cycles(machine, count):
    target = machine.cycles + count
    while machine.cycles < target: machine.step()

class TP801MachineTests(unittest.TestCase):
    def test_tpbug_boot_keypad_memory_entry(self):
        machine, clock = build()
        self.assertEqual(clock, 1996800)
        run_cycles(machine, 10000000)
        self.assertEqual(machine.read(0x2ff7), 0x11)  # TPBUG P prompt
        machine.display.sample(); run_cycles(machine, 200000)
        self.assertEqual(machine.display.sample(), [0x0c, 0x7f, 0x7f, 0x7f, 0x7f, 0x7f])
        # User enters 2000 MEM 3 E through the physical matrix.
        for row, col in [(4,1), (5,0), (5,0), (5,0), (1,0), (4,2), (5,2)]:
            row, col = 5-row, 4-col
            machine.keypad.press(row, col); run_cycles(machine, 200000)
            machine.keypad.release(row, col); run_cycles(machine, 200000)
        self.assertEqual(machine.read(0x2000), 0x3e)

    def test_prom_two_pulse_programming(self):
        machine, _ = build(); prom = machine.prom
        prom.s3_program = True; prom.set_enable(True)
        machine.write(0x1000, 0x5a)
        self.assertTrue(prom.waiting)
        prom.pulse(); self.assertEqual(machine.read(0x1000), 0xff)
        prom.pulse(); self.assertEqual(machine.read(0x1000), 0x5a)
        prom.set_enable(False)
        machine.write(0x1000, 0xff)
        self.assertEqual(machine.read(0x1000), 0x5a)

    def test_cpu_prom_write_waits_for_two_ctc_pulses(self):
        machine, _ = build(); machine.prom.s3_program = True
        machine.ctc.write_port(0x86, 0x07); machine.ctc.write_port(0x86, 1)
        machine.io_write(0x8c, 0x80)
        for offset, value in enumerate(bytes.fromhex('ed a0 76')): machine.write(0x2000 + offset, value)
        machine.write(0x2100, 0x5a)
        cpu = machine.cpu.cpu
        cpu.pc = 0x2000; cpu.hl = 0x2100; cpu.de = 0x1000; cpu.bc = 1
        machine.step()
        self.assertTrue(machine.prom.waiting)
        self.assertEqual(machine.read(0x1000), 0xff)
        run_cycles(machine, 32)
        self.assertFalse(machine.prom.waiting)
        self.assertEqual(machine.read(0x1000), 0x5a)

    def test_cassette_commands_in_monitor_open_browse_on_release(self):
        machine, _ = build()
        machine.write(0x2fff, 0x12)
        machine.cpu.cpu.pc = 0x100
        machine.cassette.request_save = Mock()
        machine.cassette.request_load = Mock()
        machine.keypad.press(4, 2)
        self.assertNotIn((4, 2), machine.keypad.keys)
        machine.cassette.request_save.assert_not_called()
        machine.keypad.release(4, 2)
        machine.cassette.request_save.assert_called_once()
        machine.keypad.press(4, 1); machine.keypad.release(4, 1)
        machine.cassette.request_load.assert_called_once()

    def test_prom_key_programs_requested_bytes(self):
        machine, _ = build()
        machine.write(0x2fff, 0x11); machine.cpu.cpu.pc = 0x100
        for address, value in zip(range(0x2ff7, 0x2ffb), (0, 0, 0, 2)): machine.write(address, value)
        machine.write(0x2000, 0x5a); machine.write(0x2001, 0xa5)
        class Root:
            def after_idle(self, callback): self.pending = callback
        root = Root(); paused = []
        machine.prom.bind_ui(root, lambda: paused.append(True)); machine.prom.s3_program = True
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / 'prom.bin'
            with patch('components.extends.tp801_prom.filedialog.asksaveasfilename', return_value=str(path)):
                machine.keypad.press(5, 4); machine.keypad.release(5, 4)
                self.assertTrue(paused); root.pending()
            self.assertEqual(path.read_bytes()[:2], b'\x5a\xa5')
            self.assertEqual(bytes(machine.prom.chips[1].data[:2]), b'\x5a\xa5')

if __name__ == '__main__': unittest.main()
