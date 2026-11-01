import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.joypad import Joypads
from components.extends.vt82c42 import VT82C42
from components.extends.sn76489 import SN76489
from platform_support.audio_output import pcm_wave
from platform_core import Machine
import io
import wave

class JoypadTests(unittest.TestCase):
    def test_active_low_and_split_p2(self):
        pad = Joypads()
        self.assertEqual((pad.read_port(0xdc), pad.read_port(0xdd)), (0xff, 0xff))
        pad.set_button(1, 'up', True)
        pad.set_button(2, 'down', True)
        pad.set_button(2, 'button1', True)
        self.assertEqual(pad.read_port(0xc0), 0x7e)
        self.assertEqual(pad.read_port(0xc1), 0xfb)
        pad.set_button(1, 'up', False)
        self.assertEqual(pad.read_port(0xdc), 0x7f)
    def test_invalid_button(self):
        with self.assertRaises(ValueError): Joypads().set_button(3, 'up', True)

class KeyboardTests(unittest.TestCase):
    def test_controller_selftest_and_command_byte(self):
        k = VT82C42(); k.write_port(0x2f, 0xaa)
        self.assertTrue(k.status() & 1); self.assertEqual(k.read_port(0x2e), 0x55)
        k.write_port(0x2f, 0x60); k.write_port(0x2e, 0x45)
        k.write_port(0x2f, 0x20); self.assertEqual(k.read_port(0x2e), 0x45)
        self.assertFalse(k.status() & 1)
    def test_scan_codes_key_disable_and_irq(self):
        k = VT82C42(); k.command_byte = 0x41
        self.assertTrue(k.key_event('a', True)); self.assertTrue(k.irq_active())
        self.assertTrue(k.key_event('a', False))
        self.assertEqual([k.read_port(0x2e), k.read_port(0x2e)], [0x1e, 0x9e])
        self.assertFalse(k.irq_active())
        k.write_port(0x2f, 0xad); self.assertFalse(k.key_event('a', True))
        k.write_port(0x2f, 0xae); self.assertTrue(k.key_event('up', True))
        self.assertEqual([k.read_port(0x2e), k.read_port(0x2e)], [0xe0, 0x48])
    def test_keyboard_commands_and_output_injection(self):
        k = VT82C42()
        k.write_port(0x2e, 0xed); k.write_port(0x2e, 5)
        self.assertEqual([k.read_port(0x2e), k.read_port(0x2e)], [0xfa, 0xfa])
        self.assertEqual(k.leds, 5)
        k.write_port(0x2f, 0xd2); k.write_port(0x2e, 0x31)
        self.assertEqual(k.read_port(0x2e), 0x31)
    def test_untranslated_scan_set_2(self):
        k = VT82C42(); k.command_byte = 0
        k.key_event('a', True); k.key_event('a', False)
        k.key_event('up', False)
        self.assertEqual([k.read_port(0x2e) for _ in range(6)], [0x1c, 0xf0, 0x1c, 0xe0, 0xf0, 0x75])

class PSGTests(unittest.TestCase):
    def test_latch_data_volume_and_tone_period(self):
        p = SN76489(cpu_hz=16000, clock_hz=16000)
        p.write_port(0x7f, 0x85); p.write_port(0x7f, 0x02)
        self.assertEqual(p.tone[0], 0x25)
        p.write_port(0x7e, 0x91); self.assertEqual(p.volume[0], 1)
        p.tick(16); initial = p.level[0]
        p.tick(16 * 0x25)
        self.assertNotEqual(p.level[0], initial)
    def test_partition_independence_and_pcm(self):
        def configured():
            p = SN76489(cpu_hz=16000, clock_hz=16000, sample_rate=1000)
            for v in (0x82, 0, 0x90, 0xe4, 0xf3): p.write_port(0x7e, v)
            return p
        a, b = configured(), configured()
        a.tick(1600)
        for _ in range(160): b.tick(10)
        self.assertEqual(list(a.samples), list(b.samples))
        self.assertEqual((a.level, a.lfsr), (b.level, b.lfsr))
        self.assertEqual(len(a.samples), 100)
    def test_noise_control_resets_lfsr(self):
        p = SN76489(); p.lfsr = 123
        p.write_port(0x7f, 0xe4)
        self.assertEqual(p.lfsr, 0x4000)
        p.advance_clocks(512)
        self.assertNotEqual(p.lfsr, 0x4000)
    def test_pcm_wave_contains_exact_samples(self):
        raw = bytes((0, 127, 255))
        with wave.open(io.BytesIO(pcm_wave(raw, 22050)), 'rb') as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 1, 22050))
            self.assertEqual(audio.readframes(3), raw)

class CPUIntegrationTests(unittest.TestCase):
    def test_cpu_accesses_all_three_devices(self):
        machine = Machine({'memory': [{'name':'RAM', 'type':'ram', 'start':0, 'size':65536}]})
        keyboard, pad, psg = VT82C42(), Joypads(), SN76489()
        machine.attach_decoded_io('keyboard', keyboard, 0x2e, 0xff, 2)
        machine.attach_decoded_io('pad', pad, 0xc0, 0xff, 2)
        machine.attach_decoded_io('PSG', psg, 0x7e, 0xff, 2)
        keyboard.key_event('a', True); pad.set_button(1, 'up', True)
        # IN A,(2E); LD (1000),A; IN A,(C0); LD (1001),A;
        # LD A,91; OUT (7E),A; HALT.
        machine.memory[0].load(bytes.fromhex('db 2e 32 00 10 db c0 32 01 10 3e 91 d3 7e 76'))
        for _ in range(7): machine.step()
        self.assertEqual(machine.read(0x1000), 0x1e)
        self.assertEqual(machine.read(0x1001), 0xfe)
        self.assertEqual(psg.volume[0], 1)

if __name__ == '__main__': unittest.main()
