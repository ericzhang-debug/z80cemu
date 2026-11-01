import sys
import unittest
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App, port_mapping_rows
from platform_core import Machine

class PortMappingTests(unittest.TestCase):
    def test_low_port_combines_high_bytes_and_tracks_latest(self):
        machine = Machine({'memory': []})
        class Device:
            def read_port(self, address): return 0x56
            def write_port(self, address, value): pass
        machine.attach_decoded_io('串口', Device(), 0x3e, 0xff)
        machine.io_write(0x123e, 0x12)
        machine.io_read(0xab3e)
        machine.io_write(0x003e, 0x78)
        self.assertEqual(machine.io_low_history[0x3e], ('写', 0x78, 0x003e))
        self.assertEqual(machine.io_low_counts[0x3e], 3)
        self.assertEqual(len(machine.io_history), 3)
        machine.reset()
        self.assertEqual(machine.io_low_history, {})
        self.assertEqual(machine.io_low_counts, {})
    def test_decoded_and_explicit_mappings(self):
        machine = Machine({'memory': []})
        a, b = SimpleNamespace(), SimpleNamespace()
        machine.attach_decoded_io('串口', a, 0x3e, 0xff, 2)
        machine.attach_io('其他', b, [0x1200, 0x1201, 0x1403])
        self.assertEqual(dict(port_mapping_rows(machine)), {
            '串口': '3E–3F（低 8 位；高 8 位任意）',
            '其他': '1200–1201, 1403',
        })
        self.assertEqual(machine.io_history, {})

    def test_nonuniform_upper_byte_is_not_mislabeled(self):
        machine = Machine({'memory': []})
        device = SimpleNamespace()
        machine.attach_io('设备', device, [0x003e, 0x013e])
        self.assertEqual(port_mapping_rows(machine)[0][1], '003E, 013E')

    def test_monitor_defaults_to_two_digit_port(self):
        machine = Machine({'memory': []}); machine.auto_open_windows = []
        class Device:
            def read_port(self, address): return 0x34
            def write_port(self, address, value): pass
        machine.attach_decoded_io('串口', Device(), 0x3e, 0xff)
        machine.io_write(0x123e, 0x42); machine.io_read(0xab3e)
        root = tk.Tk(); root.withdraw()
        with patch('app.i18n.load_language', return_value='zh'):
            app = App(root, loaded=(machine, 1000000))
        try:
            window = app.io_window(); root.update()
            def children(w):
                for child in w.winfo_children():
                    yield child
                    yield from children(child)
            table = next(w for w in children(window) if isinstance(w, ttk.Treeview))
            self.assertEqual(table.get_children(), ('3E',))
            self.assertEqual(table.item('3E', 'values'), ('串口', '读', '34', '2'))
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')): root.tk.call('after', 'cancel', identifier)
            app.close()
