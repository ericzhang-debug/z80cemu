"""TP801 matrix keypad: six row-select inputs, five active-low columns."""
import tkinter as tk
from tkinter import ttk

# The coordinates match the physical scan lines, not the displayed row order.
ROWS = (
    ('2FB8\nPROM', '2FBA\nMOVE', '2FBC\nPORT', '2FBE\nBP'),
    ('DISP\nMEM', "REG′\nREG", 'DUMP\nLAST', 'LOAD\nNEXT'),
    ('7\nH', '8\nL', '9', 'A', "MON′"),
    ('4\nIX', '5\nIY', '6\nI', 'B', 'MON'),
    ('1\nPC', '2\nSP', '3\nIFF', 'C', 'STEP'),
    ('0', 'F', 'E', 'D', 'EXEC'),
)
SHORTCUTS = {'7': (3, 4), '8': (3, 3), '9': (3, 2), 'a': (3, 1),
             '4': (2, 4), '5': (2, 3), '6': (2, 2), 'b': (2, 1),
             '1': (1, 4), '2': (1, 3), '3': (1, 2), 'c': (1, 1),
             '0': (0, 4), 'f': (0, 3), 'e': (0, 2), 'd': (0, 1)}

class TP801Keypad:
    name = 'TP801 矩阵键盘'
    pins = {**{f'ROW{i}': 'input' for i in range(6)},
            **{f'/COL{i}': 'output' for i in range(5)}, '/PROM_BOOT': 'input'}

    def __init__(self, on_press=None, on_release=None, boot_source=None):
        self.on_press = on_press or (lambda row, col: None)
        self.on_release = on_release or (lambda row, col: None)
        self.boot_source = boot_source
        self.row_mask = 0
        self.prom_boot = False
        self.keys = set()
        self.suppressed = set()

    def reset(self):
        self.row_mask = 0
        self.keys.clear()
        self.suppressed.clear()

    def set_rows(self, value): self.row_mask = value & 0x3f

    def read_columns(self):
        result = 0xdf if self.prom_boot else 0xff
        for row, col in self.keys:
            if self.row_mask & (1 << row): result &= ~(1 << col)
        return result

    def read_port(self, _address):
        if self.boot_source is not None: self.prom_boot = bool(self.boot_source())
        return self.read_columns()
    def write_port(self, _address, _value): pass

    def press(self, row, col):
        if not 0 <= row < 6 or not 0 <= col < 5: raise ValueError('无效的键盘矩阵坐标')
        if (row, col) not in self.keys:
            if self.on_press(row, col) is False:
                self.suppressed.add((row, col))
            else:
                self.keys.add((row, col))

    def release(self, row, col):
        if (row, col) in self.suppressed:
            self.suppressed.remove((row, col)); self.on_release(row, col); return
        if (row, col) in self.keys:
            self.keys.remove((row, col)); self.on_release(row, col)

    def release_all(self):
        for row, col in tuple(self.keys): self.release(row, col)
        for row, col in tuple(self.suppressed): self.release(row, col)

    def open_gui(self, root, pause):
        window = tk.Toplevel(root); window.title(self.name)
        frame = ttk.Frame(window, padding=4); frame.pack()
        for row, labels in enumerate(ROWS):
            for col, label in enumerate(labels):
                scan_row, scan_col = 5 - row, 4 - col
                button = tk.Button(frame, text=label, width=7, height=2, takefocus=False)
                button.grid(row=row, column=col, padx=1, pady=1, sticky='nsew')
                button.bind('<ButtonPress-1>', lambda event, r=scan_row, c=scan_col: self.press(r, c))
                button.bind('<ButtonRelease-1>', lambda event, r=scan_row, c=scan_col: self.release(r, c))
        held = set()
        def key_down(event):
            key = event.char.lower()
            if key in SHORTCUTS and key not in held:
                held.add(key); self.press(*SHORTCUTS[key])
        def key_up(event):
            key = event.char.lower()
            if key in held:
                held.discard(key); self.release(*SHORTCUTS[key])
        def lost_focus(_event):
            held.clear(); self.release_all()
        window.bind('<KeyPress>', key_down)
        window.bind('<KeyRelease>', key_up)
        window.bind('<FocusOut>', lost_focus)
        window.bind('<Destroy>', lost_focus)
        return window
