import sys
import unittest
from pathlib import Path
import tkinter as tk
from tkinter import ttk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from components.extends.mc6850 import MC6850

class SerialWindowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk(); self.root.withdraw()
        self.app = App(self.root, Path(__file__).resolve().parents[1] / 'machines/generic.py')
        self.serial = MC6850(0, 10000, 1000); self.serial.name = '测试串口'
    def tearDown(self):
        if self.root.winfo_exists():
            self.root.update_idletasks()
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            self.app.close()
    def widgets(self, widget):
        result = []
        for child in widget.winfo_children(): result.append(child); result.extend(self.widgets(child))
        return result
    def test_history_survives_close_multiple_windows_and_reset(self):
        self.serial.output.extend(b'Before\r\n')
        one = self.serial.open_gui(self.root, self.app.pause); self.root.update()
        view = next(w for w in self.widgets(one) if isinstance(w, tk.Text))
        self.assertIn('Before\n', view.get('1.0', 'end'))
        self.assertEqual(view.cget('state'), 'disabled')
        one.destroy(); self.serial.reset(); self.serial.output.extend(b'After\n')
        two = self.serial.open_gui(self.root, self.app.pause); self.root.update()
        view = next(w for w in self.widgets(two) if isinstance(w, tk.Text))
        self.assertIn('Before\nAfter\n', view.get('1.0', 'end'))
        self.assertEqual(bytes(self.serial.output), b'Before\r\nAfter\n')
    def test_no_separate_text_input(self):
        window = self.serial.open_gui(self.root, self.app.pause)
        widgets = self.widgets(window)
        self.assertFalse(any(isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox) for w in widgets))
    def test_transcript_is_not_truncated(self):
        self.serial.output.extend(b'x' * 70000)
        self.assertEqual(len(self.serial.output), 70000)
    def test_clear_button_and_platform_reset_clear_views(self):
        device = next(c for c in self.app.machine.components if isinstance(c, MC6850))
        window = self.app.component_windows[id(device)]
        device.output.extend(b'old')
        root = self.root
        root.after(130, root.quit); root.mainloop()
        view = next(w for w in self.widgets(window) if isinstance(w, tk.Text))
        self.assertIn('old', view.get('1.0', 'end'))
        button = next(w for w in self.widgets(window) if isinstance(w, tk.Button) and w.cget('text') == '清空')
        button.invoke()
        device.output.extend(b'new')
        root.after(130, root.quit); root.mainloop()
        self.assertEqual(view.get('1.0', 'end-1c'), 'new')
        self.app.reset()
        root.after(130, root.quit); root.mainloop()
        self.assertEqual(view.get('1.0', 'end-1c'), '')
        self.assertEqual(bytes(device.output), b'')
    def test_typing_in_terminal_sends_without_editing_history(self):
        self.serial.output.extend(b'prompt>')
        window = self.serial.open_gui(self.root, self.app.pause); self.root.update()
        view = next(w for w in self.widgets(window) if isinstance(w, tk.Text))
        view.focus_force(); self.root.update()
        view.event_generate('<KeyPress>', keysym='d'); self.root.update()
        self.serial.tick(self.serial.frame_cycles())
        self.assertEqual(self.serial.read_port(1), ord('d'))
        self.assertEqual(view.get('1.0', 'end-1c'), 'prompt>')
