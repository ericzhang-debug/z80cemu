import sys
import tempfile
import tkinter as tk
import unittest
import wave
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.msx_cassette import MSXCassette


class MSXCassetteProgressTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk(); self.root.withdraw()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tape = MSXCassette(cpu_hz=1000)
        self.pauses = []
        self.tape.bind_ui(self.root, lambda: self.pauses.append(True))

    def tearDown(self):
        if self.root.winfo_exists():
            self.tape.close_ui()
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            self.root.update_idletasks(); self.root.destroy()

    def refresh(self):
        self.root.after(230, self.root.quit)
        self.root.mainloop()

    def test_automatic_playback_opens_progress_and_confirms_selection(self):
        path = Path(self.directory.name) / 'input.wav'
        with wave.open(str(path), 'wb') as output:
            output.setnchannels(1); output.setsampwidth(1); output.setframerate(100)
            output.writeframes(bytes([0, 255] * 50))
        self.tape.set_pins(True, 0); self.tape.tick(100)
        with patch('components.extends.msx_cassette.messagebox.askyesnocancel', return_value=True), \
             patch('components.extends.msx_cassette.filedialog.askopenfilename', return_value=str(path)), \
             patch('components.extends.msx_cassette.messagebox.showinfo') as info:
            self.tape.ui_tick()
        self.assertEqual(len(self.pauses), 1)
        self.root.update()
        window = self.tape._window
        self.assertTrue(window.winfo_ismapped())
        self.assertIs(self.tape.open_gui(self.root, lambda: None), window)
        self.assertIn(str(path), info.call_args.args[1])
        self.assertIn('开始', info.call_args.args[1])
        bar = next(w for w in window.winfo_children() if isinstance(w, ttk.Progressbar))
        self.tape.tick(500); self.refresh()
        self.assertEqual(float(bar['value']), 50.0)
        self.tape.tick(500); self.refresh()
        self.assertEqual(float(bar['value']), 100.0)

    def test_recording_shows_elapsed_and_indeterminate_progress(self):
        path = Path(self.directory.name) / 'output.wav'
        with patch('components.extends.msx_cassette.messagebox.askyesnocancel', return_value=False), \
             patch('components.extends.msx_cassette.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('components.extends.msx_cassette.messagebox.showinfo') as info:
            self.tape._choose_media(self.root)
        self.assertIn(str(path), info.call_args.args[1])
        self.tape.set_pins(True, 1); self.tape.tick(1500); self.refresh()
        window = self.tape._window
        bar = next(w for w in window.winfo_children() if isinstance(w, ttk.Progressbar))
        labels = [w.cget('text') for w in window.winfo_children() if isinstance(w, ttk.Label)]
        self.assertEqual(str(bar['mode']), 'indeterminate')
        self.assertTrue(any('00:01' in label for label in labels))

    def test_cancel_and_invalid_input_do_not_confirm(self):
        with patch('components.extends.msx_cassette.messagebox.askyesnocancel', return_value=True), \
             patch('components.extends.msx_cassette.filedialog.askopenfilename', side_effect=['', 'not-a-file.wav']), \
             patch('components.extends.msx_cassette.messagebox.showinfo') as info, \
             patch('components.extends.msx_cassette.messagebox.showerror') as error:
            self.tape._choose_media(self.root)
            self.tape._choose_media(self.root)
        info.assert_not_called()
        error.assert_called_once()
        self.assertIsNone(self.tape._window)

    def test_manual_selection_pauses_confirms_and_reuses_window(self):
        window = self.tape.open_gui(self.root, lambda: self.pauses.append(True))
        frame = next(w for w in window.winfo_children() if isinstance(w, ttk.Frame))
        button = next(w for w in frame.winfo_children()
                      if isinstance(w, tk.Button) and w.cget('text') == '选择磁带…')
        path = Path(self.directory.name) / 'recording.wav'
        with patch('components.extends.msx_cassette.messagebox.askyesnocancel', return_value=False), \
             patch('components.extends.msx_cassette.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('components.extends.msx_cassette.messagebox.showinfo') as info:
            button.invoke()
        self.assertEqual(len(self.pauses), 1)
        self.assertIs(self.tape._window, window)
        self.assertEqual(len([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]), 1)
        self.assertIs(info.call_args.kwargs['parent'], window)
        self.assertIn(str(path), info.call_args.args[1])
        self.assertIn('开始', info.call_args.args[1])

    def test_close_and_reopen_cancel_progress_callbacks(self):
        window = self.tape.open_gui(self.root, lambda: None)
        self.tape.start_recording()
        self.tape.set_pins(True, 1); self.tape.tick(1500)
        self.refresh()  # Start the recording animation and periodic refresh.
        before = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertTrue(before)
        window.destroy()
        after = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertFalse(before & after, 'destroyed window must leave no progress callbacks')
        reopened = self.tape.open_gui(self.root, lambda: None)
        self.assertIsNot(reopened, window)
        self.assertTrue(reopened.winfo_exists())
        self.tape.tick(1000); self.refresh()
        before_close = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.tape.close_ui()
        after_close = set(self.root.tk.splitlist(self.root.tk.call('after', 'info')))
        self.assertFalse(before_close & after_close, 'machine close must cancel progress callbacks')


if __name__ == '__main__':
    unittest.main()
