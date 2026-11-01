import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_core import Machine
from boards.z80v2 import Z80V2
from ui.memory_model import snapshot, write_bytes, prepare_import
import tkinter as tk
from app import App

class MemoryMonitorTests(unittest.TestCase):
    def setUp(self):
        self.machine = Machine({'memory': [
            {'name':'RAM', 'type':'ram', 'start':0, 'size':2},
            {'name':'ROM', 'type':'rom', 'start':2, 'size':2}]})
    def test_read_write_protection_and_atomic_import(self):
        write_bytes(self.machine, 0, b'\x12\x34')
        with self.assertRaises(ValueError): write_bytes(self.machine, 1, b'\xaa\xbb')
        self.assertEqual([v for v, _ in snapshot(self.machine, 0, 4)], [0x12, 0x34, 0xff, 0xff])
        write_bytes(self.machine, 1, b'\xaa\xbb', True)
        self.assertEqual(snapshot(self.machine, 1, 3), [(0xaa, 'ram'), (0xbb, 'rom'), (0xff, 'rom')])
        with self.assertRaises(ValueError): write_bytes(self.machine, 3, b'\x11\x22', True)
        self.assertEqual(self.machine.read(3), 0xff)
    def test_file_lengths_and_fill(self):
        self.assertEqual(prepare_import(b'\x01\x02'), b'\x01\x02')
        self.assertEqual(prepare_import(b'\x01', 3, 0), b'\x01\x00\x00')
        self.assertEqual(prepare_import(b'\x01', 3, 255), b'\x01\xff\xff')
        self.assertEqual(prepare_import(b'\x01\x02', 1), b'\x01')
    def test_active_banked_mapping(self):
        board = Z80V2(); board.rom.load(b'\x12'); board.ram.write(0, 0x34)
        self.assertEqual(snapshot(board, 0, 1), [(0x12, 'rom')])
        board.io_write(1, 0)
        self.assertEqual(snapshot(board, 0, 1), [(0x34, 'ram')])
        write_bytes(board, 0, b'\x56')
        self.assertEqual(board.ram.read(0), 0x56)
    def test_range_and_unmapped(self):
        self.assertEqual(snapshot(self.machine, 4, 1), [(0xff, 'unmapped')])
        for start, length in ((0, 0), (0xffff, 2), (-1, 1)):
            with self.assertRaises(ValueError): snapshot(self.machine, start, length)

    def test_memory_components_share_one_window(self):
        root = tk.Tk(); root.withdraw()
        self.machine.auto_open_windows = []
        app = App(root, loaded=(self.machine, 1000000))
        try:
            ram_window = app.show_component(self.machine.memory[0])
            self.assertIs(ram_window, app.show_component(self.machine.memory[1]))
            root.update()
            text = next(w for frame in ram_window.winfo_children() for w in frame.winfo_children() if isinstance(w, tk.Text))
            self.assertIn('0000:', text.get('1.0', 'end'))
            self.assertTrue(text.tag_ranges('ram'))
            self.assertTrue(text.tag_ranges('rom'))
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')): root.tk.call('after', 'cancel', identifier)
            app.close()

    def test_closing_monitor_stops_refresh(self):
        from ui.memory_window import open_memory_window
        from ui.memory_model import snapshot as real_snapshot
        root = tk.Tk(); root.withdraw()
        try:
            with patch('ui.memory_window.snapshot', wraps=real_snapshot) as observed:
                window = open_memory_window(root, self.machine, lambda: None)
                self.assertEqual(observed.call_count, 1)
                window.destroy()
                root.after(550, root.quit); root.mainloop()
                self.assertEqual(observed.call_count, 1)
        finally:
            root.destroy()
