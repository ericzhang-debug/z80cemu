import sys
import tempfile
import tkinter as tk
import unittest
import wave
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.vtech_cassette import VTechCassette
from machines.laser310 import build
from platform_core import Machine
from app import App


class LaserTapeProgressTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk(); self.root.withdraw()
        self.cycles = 0
        self.device = VTechCassette(lambda: self.cycles, 1000)
        self.device.name = 'Laser 310 磁带'
        self.pauses = []
        self.device.bind_ui(self.root, lambda: self.pauses.append(True))
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '选择的磁带.wav'
        with wave.open(str(self.path), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(1); out.setframerate(100)
            out.writeframes(bytes([128, 224]) * 50)

    def tearDown(self):
        if self.root.winfo_exists():
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            self.root.update_idletasks()
            self.root.destroy()

    def run_ui(self):
        self.root.after(230, self.root.quit)
        self.root.mainloop()

    def test_automatic_load_opens_progress_and_confirms_selection(self):
        with patch('tkinter.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo') as info:
            self.device.request_load(); self.device.ui_tick()
            self.root.update()
        self.assertEqual(self.pauses, [True])
        window = self.device._window
        self.assertTrue(window.winfo_viewable())
        self.assertIs(self.device.open_gui(self.root, lambda: None), window)
        self.assertIn(str(self.path), info.call_args.args[1])
        self.assertIn('开始', info.call_args.args[1])
        progress = next(w for w in window.winfo_children() if isinstance(w, ttk.Progressbar))
        self.cycles = 500
        self.run_ui()
        self.assertAlmostEqual(float(progress['value']), 50.0)
        self.assertEqual(self.device.progress(), ('play', 0.5, 1.0))
        self.cycles = 1500
        self.device.input_level()
        self.run_ui()
        self.assertEqual(float(progress['value']), 100.0)

    def test_recording_progress_and_selection_confirmation(self):
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo') as info:
            self.device.request_save(); self.device.ui_tick()
            self.root.update()
        self.assertEqual(self.pauses, [True])
        self.assertIn(str(self.path), info.call_args.args[1])
        self.assertIn('开始', info.call_args.args[1])
        # Advancing before the first recorded edge is waiting, not tape time.
        self.cycles = 5000
        self.assertEqual(self.device.progress(), ('record', 0.0, None))
        self.device.output_level(True)
        self.cycles = 6234
        self.run_ui()
        self.assertEqual(self.device.progress(), ('record', 1.234, None))
        progress = next(w for w in self.device._window.winfo_children() if isinstance(w, ttk.Progressbar))
        self.assertEqual(str(progress['mode']), 'indeterminate')
        labels = [w.cget('text') for w in self.device._window.winfo_children() if isinstance(w, ttk.Label)]
        self.assertTrue(any('1.2 秒' in label for label in labels))

    def test_manual_selection_reuses_window_and_pauses(self):
        window = self.device.open_gui(self.root, lambda: self.pauses.append(True))
        bar = next(w for w in window.winfo_children() if isinstance(w, ttk.Frame))
        buttons = {w.cget('text'): w for w in bar.winfo_children() if isinstance(w, tk.Button)}
        with patch('tkinter.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo') as info:
            buttons['读取 WAV…'].invoke()
        self.assertEqual(self.pauses, [True])
        self.assertIs(self.device._window, window)
        info.assert_called_once()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo') as info:
            buttons['录制 WAV…'].invoke()
        self.assertEqual(self.pauses, [True, True])
        self.assertIs(self.device._window, window)
        info.assert_called_once()

    def test_cancel_or_invalid_wav_does_not_confirm_or_open_window(self):
        with patch('tkinter.messagebox.showinfo') as info, \
             patch('tkinter.filedialog.askopenfilename', return_value=''):
            self.device._choose_load()
            info.assert_not_called()
            self.assertIsNone(self.device._window)
        with patch('tkinter.messagebox.showinfo') as info, \
             patch('tkinter.messagebox.showerror') as error, \
             patch('tkinter.filedialog.askopenfilename', return_value=str(self.path) + '.missing'):
            self.device._choose_load()
            info.assert_not_called(); error.assert_called_once()
            self.assertIsNone(self.device._window)

    def test_destroy_cancels_refresh_and_next_selection_opens_new_window(self):
        before = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        window = self.device.open_gui(self.root, lambda: None)
        scheduled = set(self.root.tk.splitlist(self.root.tk.call('after', 'info'))) - before
        self.assertTrue(scheduled)
        window.destroy()
        self.assertIsNone(self.device._window)
        pending = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertFalse(scheduled & pending, 'destroy must cancel the old refresh callback')
        with patch('tkinter.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo'):
            self.device._choose_load()
        self.assertIsNot(self.device._window, window)
        self.assertTrue(self.device._window.winfo_exists())

    def test_machine_switch_cancels_automatic_progress_window_refresh(self):
        machine, clock = build()
        app = App(self.root, loaded=(machine, clock))
        before = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        with patch('tkinter.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('tkinter.messagebox.showinfo'):
            machine.cassette._choose_load()
        window = machine.cassette._window
        scheduled = set(self.root.tk.splitlist(self.root.tk.call('after', 'info'))) - before
        self.assertTrue(scheduled)
        replacement = Machine({'memory': []})
        replacement.auto_open_windows = []
        with patch('app.filedialog.askopenfilename', return_value='other.py'), \
             patch('app.load_machine', return_value=(replacement, clock)):
            app.open_machine()
        self.assertFalse(app.active)
        self.assertFalse(window.winfo_exists())
        self.assertIsNone(machine.cassette._window)
        pending = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertFalse(scheduled & pending, 'switch must cancel the tape refresh callback')


if __name__ == '__main__':
    unittest.main()
