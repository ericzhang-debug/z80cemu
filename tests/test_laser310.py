import sys
import tempfile
import tkinter.filedialog
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines.laser310 import build
from boards.laser310 import Laser310Machine
from app import App
from components.extends.two_bit_speaker import TwoBitSpeaker


def run_cycles(machine, count, stop_on_request=True):
    target = machine.cycles + count
    while machine.cycles < target and not (stop_on_request and machine.cassette.pending):
        machine.run_for(min(2048, target - machine.cycles))


def type_basic(machine, command):
    for char in command:
        key = {' ': 'space', '\n': 'Return'}.get(char, char)
        machine.keyboard.key_event(key, True)
        run_cycles(machine, 220000)
        machine.keyboard.key_event(key, False)
        run_cycles(machine, 220000)
        if machine.cassette.pending: break


def screen_text(machine):
    memory = machine.memory[1].data
    return '\n'.join(''.join(chr((value & 63) + 64) if (value & 63) < 32
                             else chr(value & 63) for value in memory[row * 32:(row + 1) * 32])
                     for row in range(16))


class Laser310Tests(unittest.TestCase):
    def test_backspace_edits_basic_input_in_video_window(self):
        machine, clock = build()
        root = tk.Tk(); root.withdraw()
        app = App(root, loaded=(machine, clock))
        try:
            screen = app.component_windows[id(machine.screen)]
            screen.focus_force(); root.update()
            run_cycles(machine, 10_000_000)
            for key in ('p', 'r', 'i', 'n', 't', 'space', '1', '2',
                        'BackSpace', '3', 'Return'):
                screen.event_generate('<KeyPress>', keysym=key)
                run_cycles(machine, 220_000)
                screen.event_generate('<KeyRelease>', keysym=key)
                run_cycles(machine, 220_000)
            text = screen_text(machine)
            self.assertIn('PRINT 13', text)
            self.assertIn('\n 13 ', text)
            self.assertNotIn('PRINT 12;', text)
            self.assertFalse(machine.keyboard.pressed)
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            app.close()

    def test_shifted_symbols_from_video_window_reach_basic(self):
        machine, clock = build()
        root = tk.Tk(); root.withdraw()
        app = App(root, loaded=(machine, clock))
        try:
            screen = app.component_windows[id(machine.screen)]
            screen.focus_force(); root.update()
            run_cycles(machine, 10_000_000)
            screen.event_generate('<KeyPress>', keysym='Shift_L')
            for key in ('at', 'numbersign', 'dollar', 'quotedbl', 'colon'):
                screen.event_generate('<KeyPress>', keysym=key, state=1)
                run_cycles(machine, 220_000)
                screen.event_generate('<KeyRelease>', keysym=key, state=1)
                run_cycles(machine, 220_000)
            screen.event_generate('<KeyRelease>', keysym='Shift_L', state=1)
            self.assertIn('@#$":', screen_text(machine))
            self.assertFalse(machine.keyboard.pressed)
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            app.close()

    def test_character_glyphs_are_not_mirrored(self):
        machine, _ = build()
        # The supplied MC6847 ROM stores each glyph row least-significant bit
        # first. R is asymmetric and exposes a horizontal reversal.
        machine.screen.ram[0] = 0x12
        machine.screen.ram[1] = 0x52  # inverse-video R
        pixels = machine.screen.render()
        expected = ('.####...', '.#...#..', '.#...#..', '.####...',
                    '.#.#....', '.#..#...', '.#...#..')
        for y, row in enumerate(expected, start=1):
            normal = pixels[y * 256:y * 256 + 8]
            inverse = pixels[y * 256 + 8:y * 256 + 16]
            self.assertEqual(''.join('#' if pixel == 1 else '.' for pixel in normal), row)
            self.assertEqual(''.join('.' if pixel == 1 else '#' for pixel in inverse), row)

    def test_memory_map_keyboard_and_video(self):
        machine, clock = build()
        self.assertEqual(clock, 3_546_894)
        self.assertEqual(machine.read(0x4000), 0xff)
        before = machine.read(0)
        machine.write(0, before ^ 0xff)
        self.assertEqual(machine.read(0), before)
        machine.write(0x7000, 1)
        self.assertEqual(machine.read(0x7000), 1)
        self.assertEqual(len(machine.screen.render()), 256 * 192)
        machine.keyboard.key_event('a', True)
        self.assertEqual(machine.read(0x68fd) & 0x10, 0)
        machine.keyboard.key_event('a', False)
        self.assertNotEqual(machine.read(0x68fd) & 0x10, 0)
        machine.write(0x6800, 8)
        self.assertEqual(machine.screen.mode, 8)

    def test_fast_memory_map_uses_regions_offsets_and_write_protection(self):
        machine = Laser310Machine([
            {'name': '拆分 RAM', 'type': 'ram', 'start': 0x1000, 'size': 8,
             'regions': [{'start': 0x1000, 'size': 4, 'offset': 4},
                         {'start': 0x2000, 'size': 4, 'offset': 0}]},
            {'name': 'ROM', 'type': 'rom', 'start': 0x3000, 'size': 4},
        ], 1_000_000)
        ram, rom = machine.memory
        ram.load(bytes(range(8)))
        rom.load(b'ROM!')
        for address in (*range(0x1000, 0x1004), *range(0x2000, 0x2004),
                        *range(0x3000, 0x3004)):
            self.assertEqual(machine.read(address), machine.resolve_memory(address).read(address))
        self.assertEqual([machine.read(a) for a in (0x1000, 0x2000)], [4, 0])
        machine.write(0x1001, 0xa5)
        machine.write(0x2001, 0x5a)
        machine.write(0x3000, 0)
        self.assertEqual(ram.data[5], 0xa5)
        self.assertEqual(ram.data[1], 0x5a)
        self.assertEqual(machine.read(0x3000), ord('R'))
        self.assertEqual(machine.read(0x4000), 0xff)

    def test_arrow_keys_preserve_other_held_keys(self):
        machine, _ = build()
        keyboard = machine.keyboard
        for arrow, key in (('Left', 'm'), ('Right', 'comma'), ('Up', 'period'), ('Down', 'space'),
                           ('BackSpace', 'm'), ('Delete', 'm')):
            keyboard.key_event('Control_L', True)
            keyboard.key_event(arrow, True)
            self.assertEqual(keyboard.pressed, {'control', key})
            keyboard.key_event(arrow, False)
            self.assertEqual(keyboard.pressed, {'control'})
            keyboard.key_event('Control_L', False)
            self.assertFalse(keyboard.pressed)

    def test_differential_speaker_levels_and_timing(self):
        clock = [0]
        speaker = TwoBitSpeaker(lambda: clock[0], 1000, 1000)
        for a, b, expected in ((0, 0, 128), (1, 0, 224), (0, 1, 32), (1, 1, 128)):
            speaker.set_inputs(a, b)
            self.assertEqual(speaker.level, expected)
            clock[0] += 3
            speaker._advance()
            self.assertEqual(list(speaker.samples)[-3:], [expected] * 3)
        machine, _ = build()
        machine.write(0x6800, 1)
        self.assertEqual(machine.speaker.level, 224)
        machine.write(0x6800, 0x20)
        self.assertEqual(machine.speaker.level, 32)

    def test_reset_and_close_save_recorded_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            for action in ('reset', 'close_ui'):
                machine, _ = build()
                tape = Path(directory) / (action + '.wav')
                machine.cassette.start_recording(tape)
                machine.cassette.output_level(True)
                machine.cycles += 10000
                machine.cassette.output_level(False)
                getattr(machine.cassette, action)()
                with wave.open(str(tape), 'rb') as recorded:
                    self.assertGreater(recorded.getnframes(), 0)
                self.assertIsNone(machine.cassette.output_path)

    def test_basic_boot_and_cassette_round_trip(self):
        machine, _ = build()
        run_cycles(machine, 10_000_000)
        self.assertIn('VIDEO TECHNOLOGY', screen_text(machine))
        self.assertIn('BASIC V2.0', screen_text(machine))
        self.assertIn('READY', screen_text(machine))
        type_basic(machine, '10 print 1\n')
        type_basic(machine, 'csave\n')
        run_cycles(machine, 2_000_000)
        self.assertEqual(machine.cassette.pending, 'save')
        with tempfile.TemporaryDirectory() as directory:
            tape = Path(directory) / 'recorded.wav'
            machine.cassette.pending = None
            machine.cassette.start_recording(tape)
            for _ in range(300):
                run_cycles(machine, 250_000, False)
                machine.cassette.ui_tick()
                if machine.cassette.output_path is None: break
            self.assertTrue(tape.exists(), 'CSAVE must finish and write a WAV')

            loaded, _ = build()
            run_cycles(loaded, 10_000_000)
            type_basic(loaded, 'cload\n')
            run_cycles(loaded, 2_000_000)
            self.assertEqual(loaded.cassette.pending, 'load')
            loaded.cassette.pending = None
            loaded.cassette.load_wav(tape)
            run_cycles(loaded, 30_000_000, False)
            type_basic(loaded, 'list\n')
            run_cycles(loaded, 2_000_000, False)
            self.assertIn('10 PRINT 1', screen_text(loaded))

    def test_cancelled_dialog_can_be_requested_on_next_command(self):
        machine, _ = build()
        class Root:
            def after_idle(self, callback): callback()
        machine.cassette.bind_ui(Root(), lambda: None)
        with patch('tkinter.filedialog.askopenfilename', return_value='') as load, \
             patch('tkinter.filedialog.asksaveasfilename', return_value='') as save:
            machine.cassette.request_load(); machine.cassette.ui_tick()
            machine.cassette.request_load(); machine.cassette.ui_tick()
            self.assertEqual(load.call_count, 1)
            machine.cpu.cpu.pc = 0x2f00
            machine.read(0x68fd)
            machine.cassette.request_load(); machine.cassette.ui_tick()
            self.assertEqual(load.call_count, 2)
            machine.cassette.request_save(); machine.cassette.ui_tick()
            machine.cassette.request_save(); machine.cassette.ui_tick()
            self.assertEqual(save.call_count, 1)
            machine.read(0x68fd)
            machine.cassette.request_save(); machine.cassette.ui_tick()
            self.assertEqual(save.call_count, 2)


if __name__ == '__main__':
    unittest.main()
