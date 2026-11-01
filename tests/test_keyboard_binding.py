import sys
import tkinter as tk
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from platform_core import Machine
from components.extends.vt82c42 import VT82C42
from components.extends.tms9918a import TMS9918A

class KeyboardBindingTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk(); self.root.withdraw()
        self.machine = Machine({'memory': []})
        self.keyboard = VT82C42(0x20); self.screen = TMS9918A(0x30)
        self.machine.attach_io('键盘', self.keyboard, [0x20, 0x21])
        self.machine.attach_io('屏幕', self.screen, [0x30, 0x31])
        self.machine.bind_keyboard(self.keyboard, self.screen)
        self.machine.auto_open_windows = ['屏幕', '键盘']
        self.app = App(self.root, loaded=(self.machine, 1000000))
    def tearDown(self):
        if self.root.winfo_exists():
            self.root.update_idletasks()
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            self.app.close()
    def test_key_events_are_routed_to_configured_screen(self):
        self.assertNotIn(id(self.keyboard), self.app.component_windows)
        self.assertIsNone(self.app.show_component(self.keyboard))
        screen = self.app.component_windows[id(self.screen)]
        screen.focus_force(); self.root.update()
        screen.event_generate('<KeyPress>', keysym='a')
        screen.event_generate('<KeyRelease>', keysym='a')
        self.root.update()
        self.assertEqual(list(self.keyboard.output), [0x1e, 0x9e])
    def test_reopened_screen_retains_binding(self):
        self.app.component_windows[id(self.screen)].destroy()
        screen = self.app.show_component(self.screen)
        screen.focus_force(); self.root.update()
        screen.event_generate('<KeyPress>', keysym='a'); self.root.update()
        self.assertEqual(self.keyboard.read_port(0x20), 0x1e)
    def test_shifted_key_release_uses_original_physical_key(self):
        screen = self.app.component_windows[id(self.screen)]
        screen.focus_force(); self.root.update()
        screen.event_generate('<KeyPress>', keysym='Shift_L')
        screen.event_generate('<KeyPress>', keysym='at', state=1)
        screen.event_generate('<KeyRelease>', keysym='Shift_L', state=1)
        screen.event_generate('<KeyRelease>', keysym='2', state=0)
        self.assertEqual(list(self.keyboard.output), [0x2a, 0x03, 0xaa, 0x83])
    def test_binding_requires_attached_devices(self):
        with self.assertRaises(ValueError): self.machine.bind_keyboard(VT82C42(), self.screen)
        with self.assertRaises(ValueError): self.machine.bind_keyboard(self.keyboard, self.screen)
