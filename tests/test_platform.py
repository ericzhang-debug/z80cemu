import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_core import Machine
from components.extends.z80_ctc import Z80CTC
from components.extends.z80_pio import Z80PIO
from platform_support.logic import decoder, multiplexer
from components.extends.mc6850 import MC6850
from platform_support.signals import Net, SignalConflict

class PlatformTests(unittest.TestCase):
    def machine(self):
        return Machine({'memory': [{'name': 'ROM', 'type': 'rom', 'start': 0, 'size': 256},
                                   {'name': 'RAM', 'type': 'ram', 'start': 256, 'size': 256}]})
    def test_cpu_executes_and_rom_protects(self):
        m = self.machine()
        # LD A,42; LD (0100),A; HALT
        m.memory[0].load(bytes.fromhex('3e 42 32 00 01 76'))
        for _ in range(3): m.step()
        self.assertEqual(m.read(0x100), 0x42)
        m.write(0, 0)
        self.assertEqual(m.read(0), 0x3e)
        self.assertEqual(m.read(0x200), 0xff)
    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            Machine({'memory': [{'name': 'a', 'type': 'ram', 'start': 0, 'size': 10},
                                {'name': 'b', 'type': 'rom', 'start': 9, 'size': 10}]})
    def test_io_device(self):
        m = self.machine()
        class Device:
            def read_port(self, address): return 0x35
            def write_port(self, address, value): self.value = value
        d = Device(); m.attach_io('test', d, [0x12])
        m.io_write(0x12, 0x44)
        self.assertEqual(d.value, 0x44)
        self.assertEqual(m.io_read(0x12), 0x35)
        self.assertEqual(m.io_history[0x12], ('读', 0x35))

    def test_cpu_io_address_decoding(self):
        m = self.machine()
        class Device:
            def read_port(self, address): return 0x57
            def write_port(self, address, value): self.written = (address, value)
        d = Device(); m.attach_decoded_io('test', d, 0x10, 0xff)
        # Z80 immediate I/O uses A as the upper address byte.
        m.memory[0].load(bytes.fromhex('3e 42 d3 10 db 10 32 00 01 76'))
        for _ in range(5): m.step()
        self.assertEqual(d.written, (0x4210, 0x42))
        self.assertEqual(m.read(0x100), 0x57)
        with self.assertRaises(ValueError): m.attach_io('conflict', Device(), [0x4210])

    def test_ctc_timer_and_interrupt_priority(self):
        m = self.machine(); pulses = []
        ctc = Z80CTC(0x10, lambda channel, count: pulses.append((channel, count)))
        m.attach_decoded_io('CTC', ctc, 0x10, 0xff, 4)
        m.io_write(0x10, 0xe0)  # vector
        m.io_write(0x10, 0x85)  # interrupt, timer, constant follows
        m.io_write(0x10, 2)
        ctc.tick(36)
        self.assertEqual(pulses, [(0, 1)])
        self.assertEqual(m.acknowledge(), 0xe0)
        self.assertIsNone(m.interrupt_candidate())
        m.reti(); self.assertFalse(ctc.in_service())

    def test_pio_bit_control(self):
        pio = Z80PIO(0x14)
        pio.write_port(0x16, 0xcf)  # port A mode 3
        pio.write_port(0x16, 0xf0)  # upper nibble input
        pio.write_port(0x14, 0x05)
        pio.ports[0].set_inputs(0xa0)
        self.assertEqual(pio.read_port(0x14), 0xa5)

    def test_memory_load_bounds_and_reset(self):
        m = self.machine()
        m.memory[1].load(b'abc', 253)
        with self.assertRaises(ValueError): m.memory[1].load(b'abcd', 253)
        m.reset()
        self.assertEqual(m.memory[1].data[-3:], b'abc')

    def test_logic_helpers(self):
        self.assertEqual(decoder(2, 2), (True, True, False, True))
        self.assertEqual(multiplexer([3, 8], 1), 8)

    def test_cpu_transmits_via_acia(self):
        m = self.machine(); acia = MC6850(0x18, 1000, 1000)
        m.attach_decoded_io('ACIA', acia, 0x18, 0xff, 2)
        # Configure 8N1, transmit 'Z', then let its frame finish.
        m.memory[0].load(bytes.fromhex('3e 14 d3 18 3e 5a d3 19 00 00 76'))
        for _ in range(6): m.step()
        self.assertEqual(bytes(acia.output), b'Z')
        self.assertGreater(m.io_counts[0x5a19], 0)

    def test_signal_net_rejects_contention_without_changing_state(self):
        net = Net('IRQ', pull=1); seen = []; net.connect(seen.append)
        net.drive('device-a', 0)
        with self.assertRaises(SignalConflict): net.drive('device-b', 1)
        self.assertEqual(net.value, 0)
        net.drive('device-a', None)
        self.assertEqual(seen, [1, 0, 1])

    def test_cpu_reports_device_callback_errors(self):
        m = self.machine()
        class Broken:
            def read_port(self, address): raise ValueError('broken device')
            def write_port(self, address, value): pass
        m.attach_decoded_io('broken', Broken(), 0x10, 0xff)
        m.memory[0].load(bytes.fromhex('db 10'))
        with self.assertRaisesRegex(RuntimeError, '总线回调失败') as result:
            m.step()
        self.assertIsInstance(result.exception.__cause__, ValueError)

if __name__ == '__main__': unittest.main()
