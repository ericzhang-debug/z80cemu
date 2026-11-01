import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines.msx import build, CLOCK_HZ
from machines.msx_cbios import build as build_cbios
from components.extends.i8255 import I8255
from components.extends.msx_keyboard import MSXKeyboard
from components.extends.tms9918a import TMS9918A
from components.extends.ay_3_8910 import AY38910
from components.extends.joypad import Joypads
from components.extends.msx_cassette import MSXCassette


def component(machine, kind): return next(item for item in machine.components if isinstance(item, kind))
def run(machine, cycles):
    end = machine.cycles + cycles
    while machine.cycles < end: machine.run_for(2048)
def run_until(machine, condition, cycles):
    end = machine.cycles + cycles
    while machine.cycles < end and not condition(): machine.run_for(1024)


class MSXMachineTests(unittest.TestCase):
    def test_slots_keyboard_and_joystick_wiring(self):
        machine, hz = build()
        self.assertEqual(hz, CLOCK_HZ)
        ppi = component(machine, I8255)
        keyboard = component(machine, MSXKeyboard)
        psg = component(machine, AY38910)
        joy = component(machine, Joypads)
        original = machine.read(0)
        ppi.write_port(0xab, 0x82)  # A,C output; B input
        ppi.write_port(0xa8, 0xff)  # all pages in RAM slot 3
        machine.write(0, 0x42)
        self.assertEqual(machine.read(0), 0x42)
        ppi.write_port(0xa8, 0)
        self.assertEqual(machine.read(0), original)
        keyboard.key_event('a', True)
        ppi.write_port(0xaa, 2)
        self.assertEqual(ppi.read_port(0xa9), 0xbf)
        keyboard.key_event('a', False)
        self.assertEqual(ppi.read_port(0xa9), 0xff)
        ppi.write_port(0xab, 0x03)  # set PC1 (row 2)
        self.assertEqual(ppi.read_port(0xaa) & 15, 2)
        joy.set_button(2, 'left', True)
        psg.write_port(0xa0, 7); psg.write_port(0xa1, 0x80)
        psg.write_port(0xa0, 15); psg.write_port(0xa1, 0x40)
        psg.write_port(0xa0, 14)
        self.assertEqual(psg.read_port(0xa2) & 0x3f, 0x3b)

    def test_cbios_boots_and_echoes_keyboard_through_rom_cartridge(self):
        machine, _ = build_cbios()
        # Real cartridge entry calls C-BIOS CHGET and CHPUT in a loop.
        machine.cartridge.insert(b'AB\x10\x40' + bytes(12) + bytes.fromhex('CD 9F 00 CD A2 00 18 F8'))
        machine.reset()
        video, keyboard = component(machine, TMS9918A), component(machine, MSXKeyboard)
        run(machine, 21_000_000)
        self.assertIn(b'C-BIOS 0.29', bytes(video.vram))
        self.assertIn(b'Init ROM in slot: 1', bytes(video.vram))
        self.assertTrue(video.registers[1] & 0x40)
        self.assertGreater(len(set(video.render())), 1)
        before = bytes(video.vram)
        keyboard.key_event('a', True)
        run(machine, 2_000_000)
        keyboard.key_event('a', False)
        run(machine, 300_000)
        self.assertNotEqual(bytes(video.vram), before)
        self.assertIn(b'Init ROM in slot: 1             a', bytes(video.vram))

    def test_rainbios_boots_basic_and_evaluates_typed_command(self):
        machine, _ = build()
        machine.reset()
        video, keyboard = component(machine, TMS9918A), component(machine, MSXKeyboard)
        run(machine, 16_000_000)
        self.assertIn(b'BASIC', bytes(video.vram))
        keyboard.key_event('shift_l', True)
        for key in 'print':
            keyboard.key_event(key, True); run(machine, 140_000)
            keyboard.key_event(key, False); run(machine, 100_000)
        keyboard.key_event('shift_l', False)
        for key in ('space', '2', 'return'):
            keyboard.key_event(key, True); run(machine, 140_000)
            keyboard.key_event(key, False); run(machine, 100_000)
        run(machine, 500_000)
        self.assertIn(b'>PRINT 2', bytes(video.vram))
        self.assertIn(b'         2', bytes(video.vram))

        keyboard.key_event('Shift_L', True)
        for key in ('at', 'numbersign', 'dollar', 'quotedbl', 'colon'):
            keyboard.key_event(key, True); run(machine, 140_000)
            keyboard.key_event(key, False); run(machine, 100_000)
        keyboard.key_event('Shift_L', False)
        self.assertIn(b'@#$":', bytes(video.vram))

        # Execute the firmware's actual tape routines, not host-side FSK
        # encoding.  Record a byte as WAV, then decode it via the BIOS.
        tape = component(machine, MSXCassette)
        tape.start_recording()
        output = bytes.fromhex('F3 31 00 F0 AF CD EA 00 3E 42 CD ED 00 CD F0 00 3E 55 32 00 90 76')
        machine.ram.data[0x8000:0x8000 + len(output)] = output
        machine.ram.data[0x9000] = 0
        machine.cpu.cpu.pc = 0x8000
        run_until(machine, lambda: machine.ram.data[0x9000] == 0x55, 3_000_000)
        self.assertEqual(machine.ram.data[0x9000], 0x55)
        self.assertGreater(len(tape.wav_bytes()), 1000)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tape.wav'
            tape.save_wav(path)
            tape.load_wav(path)
            reader = bytes.fromhex('F3 31 00 F0 CD E1 00 38 0C CD E4 00 38 07 32 01 90 CD E7 00 3E 55 32 02 90 76')
            machine.ram.data[0x8000:0x8000 + len(reader)] = reader
            machine.ram.data[0x9001:0x9003] = b'\0\0'
            machine.cpu.cpu.pc = 0x8000
            run_until(machine, lambda: machine.ram.data[0x9002] == 0x55, 3_000_000)
            self.assertEqual(machine.ram.data[0x9002], 0x55)
            self.assertEqual(machine.ram.data[0x9001], 0x42)

    def test_plain_cartridge_rejects_unsupported_mapper_size(self):
        machine, _ = build()
        with self.assertRaises(ValueError): machine.cartridge.insert(bytes(0x8001))
        self.assertFalse(machine.cartridge.inserted)


class AY38910Tests(unittest.TestCase):
    def test_register_masks_tone_audio_and_port_directions(self):
        sent = []
        psg = AY38910(read_a=lambda: 0x53, write_b=sent.append)
        def write(reg, value):
            psg.write_port(0xa0, reg); psg.write_port(0xa1, value)
        write(1, 0xff)
        self.assertEqual(psg.read_port(0xa2), 0x0f)
        write(7, 0x80); write(15, 0x40)
        self.assertEqual(sent, [0x00, 0x40])
        psg.write_port(0xa0, 14)
        self.assertEqual(psg.read_port(0xa2), 0x53)
        write(0, 10); write(1, 0); write(7, 0xbe); write(8, 15)
        psg.sample_rate = 22050
        psg.tick(100_000)
        self.assertGreater(len(set(psg.samples)), 1)


class CassetteTests(unittest.TestCase):
    def test_motor_requests_media_once_and_pauses(self):
        tape = MSXCassette(cpu_hz=1000)
        pauses = []
        tape.bind_ui(object(), lambda: pauses.append(True))
        tape.set_pins(True, 0)
        tape.tick(99)
        with patch('components.extends.msx_cassette.messagebox.askyesnocancel', return_value=None) as dialog:
            tape.ui_tick()
            self.assertFalse(dialog.called)
            tape.tick(1)
            tape.ui_tick(); tape.ui_tick()
            self.assertEqual(dialog.call_count, 1)
            self.assertEqual(pauses, [True])


if __name__ == '__main__': unittest.main()
