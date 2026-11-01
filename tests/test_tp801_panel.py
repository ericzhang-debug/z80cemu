import sys
import tkinter as tk
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.tp801_display import TP801Display
from components.extends.tp801_keypad import TP801Keypad, ROWS

class TP801PanelTests(unittest.TestCase):
    def test_key_matrix_rows_and_active_low(self):
        events = []
        keypad = TP801Keypad(on_press=lambda row, col: events.append((row, col)))
        for gui_row, labels in enumerate(ROWS):
            for gui_col, _ in enumerate(labels):
                row, col = 5 - gui_row, 4 - gui_col
                keypad.press(row, col); keypad.press(row, col)
                keypad.set_rows(1 << row)
                self.assertEqual(keypad.read_columns(), 0xff & ~(1 << col))
                keypad.set_rows(0)
                self.assertEqual(keypad.read_columns(), 0xff)
                keypad.release(row, col)
        self.assertEqual(len(events), sum(map(len, ROWS)))
        keypad.prom_boot = True
        self.assertEqual(keypad.read_columns(), 0xdf)

    def test_display_multiplex_integration(self):
        display = TP801Display()
        for index in range(6):
            display.set_digits(1 << (5 - index))
            display.set_segments(0x40 | index)
            display.tick(100)
        self.assertEqual(display.sample(), [0x40 | i for i in range(6)])
        self.assertEqual(display.sample(), [0x7f] * 6)

    def test_independent_gui_windows(self):
        root = tk.Tk(); root.withdraw()
        keypad, display = TP801Keypad(), TP801Display()
        try:
            key_window = keypad.open_gui(root, lambda: None)
            display_window = display.open_gui(root, lambda: None)
            root.update_idletasks()
            self.assertTrue(key_window.winfo_exists())
            self.assertTrue(display_window.winfo_exists())
        finally:
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')): root.tk.call('after', 'cancel', identifier)
            root.destroy()

if __name__ == '__main__': unittest.main()
