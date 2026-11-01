import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boards.z80v2 import Z80V2
from components.extends.mc6850 import MC6850
from machines.tp801 import build as build_tp801

class BatchExecutionTests(unittest.TestCase):
    def pair(self):
        first, second = Z80V2(), Z80V2()
        # Enable IM 1 and loop; the VDP generates an interrupt after 100 cycles.
        program = bytes.fromhex('ed 56 fb 00 00 18 fc')
        for machine in (first, second):
            machine.rom.load(program)
            machine.rom.load(bytes.fromhex('fb c9'), 0x38)  # EI; RET
            video = machine.ports[0xbe]
            video.cpu_hz = 6000
            video.write_port(0xbf, 0x20); video.write_port(0xbf, 0x81)
        return first, second

    def test_video_interrupt_timing_matches_single_instruction(self):
        reference, accelerated = self.pair()
        target = 4000
        while reference.cycles < target: reference.step()
        while accelerated.cycles < target: accelerated.run_for(target - accelerated.cycles)
        a, b = reference.cpu.cpu, accelerated.cpu.cpu
        self.assertEqual((accelerated.cycles, b.pc, b.sp, b.iff1, b.iff2),
                         (reference.cycles, a.pc, a.sp, a.iff1, a.iff2))
        self.assertEqual(accelerated.ports[0xbe].status, reference.ports[0xbe].status)
        self.assertEqual(accelerated.ram.data, reference.ram.data)

    def test_serial_irq_deadline_and_io_break(self):
        device = MC6850(0x30, 10000, 1000)
        device.write_port(0x30, 0x94); device.send(b'A')
        self.assertEqual(device.batch_irq_deadline(), device.frame_cycles())
        device.tick(device.frame_cycles())
        self.assertTrue(device.irq_active())
        self.assertIsNone(device.batch_irq_deadline())

    def test_enabling_and_acknowledging_video_irq_during_io(self):
        reference, accelerated = Z80V2(), Z80V2()
        # Program R1 through OUT, enable IM1, and clear VDP status in the ISR.
        code = bytes.fromhex('3e 20 d3 bf 3e 81 d3 bf ed 56 fb 00 18 fd')
        for machine in (reference, accelerated):
            machine.rom.load(code)
            machine.rom.load(bytes.fromhex('db bf fb ed 4d'), 0x38)
            machine.ports[0xbe].cpu_hz = 6000
        target = 4000
        while reference.cycles < target: reference.step()
        while accelerated.cycles < target: accelerated.run_for(target - accelerated.cycles)
        a, b = reference.cpu.cpu, accelerated.cpu.cpu
        self.assertEqual((accelerated.cycles, b.pc, b.sp, b.af, b.iff1),
                         (reference.cycles, a.pc, a.sp, a.af, a.iff1))
        self.assertEqual(accelerated.ports[0xbe].status, reference.ports[0xbe].status)
        self.assertEqual(accelerated.io_counts, reference.io_counts)

    def test_unknown_clocked_component_uses_instruction_steps(self):
        machine = Z80V2()
        class Unknown:
            def read_port(self, address): return 0xff
            def write_port(self, address, value): pass
            def tick(self, cycles): pass
        machine.attach_io('unknown', Unknown(), [0x1234])
        self.assertFalse(machine._can_batch())
        self.assertLessEqual(machine.run_for(2000), 25)

    def test_tp801_batch_matches_step_across_keypad_and_display_io(self):
        reference, _ = build_tp801(); accelerated, _ = build_tp801()
        # Fixed cycle checkpoints are stopped on instruction boundaries in both.
        for key in (None, (1, 4), None):
            for machine in (reference, accelerated):
                if key: machine.keypad.press(*key)
                else: machine.keypad.release_all()
            target = reference.cycles + 120000
            while reference.cycles < target: reference.step()
            while accelerated.cycles < target: accelerated.run_for(target - accelerated.cycles)
            a, b = reference.cpu.cpu, accelerated.cpu.cpu
            self.assertEqual((reference.cycles, a.pc, a.sp, a.af, a.bc, a.hl),
                             (accelerated.cycles, b.pc, b.sp, b.af, b.bc, b.hl))
            self.assertEqual(reference.memory[1].data, accelerated.memory[1].data)
            self.assertEqual(reference.display.sample(), accelerated.display.sample())

    def test_tp801_timer_starts_at_same_io_cycle(self):
        reference, _ = build_tp801(); accelerated, _ = build_tp801()
        for machine in (reference, accelerated):
            machine.ctc.write_port(0x84, 0x07)
            for i, value in enumerate(bytes.fromhex('3e 01 d3 84 76')):
                machine.write(0x2000 + i, value)
            machine.cpu.cpu.pc = 0x2000
        while reference.cycles < 18: reference.step()
        while accelerated.cycles < 18: accelerated.run_for(18 - accelerated.cycles)
        a, b = reference.ctc.core.channels[0], accelerated.ctc.core.channels[0]
        self.assertEqual((a.count, a.phase, a.running), (b.count, b.phase, b.running))
