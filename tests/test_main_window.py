import sys
import unittest
from unittest.mock import patch
from pathlib import Path
import tkinter as tk
from tkinter import ttk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App, tile_rectangles
from platform_core import Machine
from components.extends.mc6850 import MC6850

class MainWindowTests(unittest.TestCase):
    def setUp(self):
        language_patch = patch('app.i18n.load_language', return_value='zh')
        language_patch.start(); self.addCleanup(language_patch.stop)
        self.root = tk.Tk(); self.root.withdraw()
        self.machine = Machine({'memory': []})
        self.a, self.b = MC6850(0x10), MC6850(0x20)
        self.machine.attach_io('串口', self.a, [0x10, 0x11])
        self.machine.attach_io('串口', self.b, [0x20, 0x21])
        class NoGUI:
            def read_port(self, address): return 0xff
            def write_port(self, address, value): pass
        self.none = NoGUI(); self.machine.attach_io('无界面', self.none, [0x30])
    def tearDown(self):
        if self.root.winfo_exists():
            self.root.update_idletasks()
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            if hasattr(self, 'app'): self.app.close()
            else: self.root.destroy()
    def test_default_opens_each_supported_window_and_names_instances(self):
        self.app = App(self.root, loaded=(self.machine, 3210000))
        self.assertEqual((self.a.name, self.b.name), ('串口', '串口 (2)'))
        self.assertEqual(self.app.clock_hz, 3210000)
        self.assertEqual(self.app.component_windows[id(self.a)].title(), '串口 终端')
        self.assertEqual(self.app.component_windows[id(self.b)].title(), '串口 (2) 终端')
        self.root.update_idletasks()
        self.assertEqual(tuple(map(int, self.app.component_windows[id(self.a)].resizable())), (1, 1))
        self.assertNotIn(id(self.none), self.app.component_windows)
        self.assertIsNone(self.app.show_component(self.none))
        self.assertIs(self.app.show_component(self.a), self.app.component_windows[id(self.a)])
    def test_window_selection_and_main_buttons(self):
        self.machine.auto_open_windows = ['串口 (2)']
        self.app = App(self.root, loaded=(self.machine, 2500000))
        self.assertEqual(set(self.app.component_windows), {id(self.b)})
        def children(widget):
            for child in widget.winfo_children():
                if not isinstance(child, tk.Toplevel):
                    yield child
                    yield from children(child)
        buttons = [w.cget('text') for w in children(self.root) if isinstance(w, tk.Button)]
        self.assertEqual(buttons, ['开始'])
        self.assertEqual(self.app.status.cget('fg'), 'red')
        self.app.toggle_run()
        self.assertEqual(self.app.run_button.cget('text'), '暂停')
        self.assertEqual(self.app.status.cget('fg'), 'green')
        self.machine.cycles += 1000000
        self.app.sample_speed(self.app._speed_time + 2)
        self.app.refresh()
        self.assertEqual(self.app.frequency_label.cget('text'), '实际频率：0.500 MHz')
        self.app.toggle_run()
        self.assertEqual(self.app.run_button.cget('text'), '开始')
        self.assertEqual(self.app.frequency_label.cget('text'), '实际频率：0.000 MHz')
        self.assertNotIn('PC', self.app.status.cget('text'))
        self.assertNotIn('周期', self.app.status.cget('text'))
        with patch('app.simpledialog.askstring', return_value='3.579545'):
            self.app.set_clock()
        self.assertEqual(self.app.clock_hz, 3579545)
        self.assertEqual(self.a.cpu_hz, 3579545)

    def test_tile_rectangles_do_not_overlap(self):
        rectangles = tile_rectangles(7, 1920, 1080)
        self.assertEqual(len(rectangles), 7)
        for i, (w, h, x, y) in enumerate(rectangles):
            self.assertGreater(w, 0); self.assertGreater(h, 0)
            self.assertLessEqual(x + w, 1920); self.assertLessEqual(y + h, 1080)
            for other_w, other_h, other_x, other_y in rectangles[i + 1:]:
                self.assertTrue(x + w <= other_x or other_x + other_w <= x or y + h <= other_y or other_y + other_h <= y)

    def test_tiling_keeps_small_preferred_sizes(self):
        sizes = [(180, 100), (240, 140), (160, 90)]
        rectangles = tile_rectangles(len(sizes), 1920, 1080, sizes)
        self.assertEqual([(w, h) for w, h, _, _ in rectangles], sizes)
        self.assertLess(rectangles[-1][2] + rectangles[-1][0], 700)

if __name__ == '__main__': unittest.main()
