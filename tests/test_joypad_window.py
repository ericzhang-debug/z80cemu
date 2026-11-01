import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.joypad import Joypads


class JoypadWindowTests(unittest.TestCase):
    def test_layout_and_button_events_for_both_players(self):
        root = tk.Tk()
        root.withdraw()
        pad = Joypads()
        window = pad.open_gui(root, lambda: None)
        try:
            root.update()
            frames = [child for child in window.winfo_children() if isinstance(child, ttk.LabelFrame)]
            self.assertEqual(len(frames), 2)
            expected = {'上': ('up', 0, 1), '左': ('left', 1, 0),
                        '右': ('right', 1, 2), '下': ('down', 2, 1),
                        '1': ('button1', 1, 4), '2': ('button2', 1, 5)}
            for player, frame in enumerate(frames):
                buttons = {button.cget('text'): button for button in frame.winfo_children()}
                self.assertEqual(set(buttons), set(expected))
                for label, (key, row, column) in expected.items():
                    button = buttons[label]
                    self.assertEqual((button.grid_info()['row'], button.grid_info()['column']), (row, column))
                    button.event_generate('<ButtonPress-1>')
                    self.assertEqual(pad.pressed[player], {key})
                    self.assertFalse(pad.pressed[1 - player])
                    button.event_generate('<ButtonRelease-1>')
                    self.assertFalse(pad.pressed[player])
        finally:
            window.destroy()
            root.update_idletasks()
            root.destroy()


if __name__ == '__main__':
    unittest.main()
