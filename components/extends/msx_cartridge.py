"""Plain MSX ROM cartridge, up to 32 KiB; bank-switched mappers are separate hardware."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

class MSXCartridge:
    pins = {**{f'A{i}': 'input' for i in range(16)},
            **{f'D{i}': 'output' for i in range(8)}, '/CS': 'input', '/RD': 'input'}
    name = 'MSX 卡带'
    readonly = True
    start, size = 0x4000, 0x8000
    regions = [{'start': 0x4000, 'size': 0x8000, 'offset': 0}]

    def __init__(self, on_change=None):
        self.data = bytearray([0xff] * self.size)
        self.inserted = False
        self.path = None
        self.on_change = on_change or (lambda: None)

    def contains(self, address): return 0x4000 <= address < 0xc000 and self.inserted
    def offset(self, address): return address - 0x4000
    def read(self, address): return self.data[self.offset(address)]
    def write(self, address, value): pass
    def insert(self, data, path=None):
        if not data or len(data) > self.size:
            raise ValueError('普通 MSX 卡带大小必须为 1 至 32768 字节；不支持 bank mapper')
        self.data[:] = b'\xff' * self.size
        self.data[:len(data)] = data
        self.path, self.inserted = path, True
    def eject(self):
        self.inserted, self.path = False, None
        self.data[:] = b'\xff' * self.size

    def open_gui(self, root, pause):
        window = tk.Toplevel(root); window.title(self.name)
        label = ttk.Label(window, text=''); label.pack(padx=5, pady=4)
        def refresh(): label.config(text=str(self.path) if self.inserted else '未插入卡带')
        def insert():
            pause()
            path = filedialog.askopenfilename(parent=window, title='选择 MSX 卡带 ROM',
                                              filetypes=[('MSX ROM', '*.rom *.bin'), ('所有文件', '*.*')])
            if not path: return
            try:
                self.insert(Path(path).read_bytes(), path)
                self.on_change()
                refresh()
            except (OSError, ValueError) as error:
                messagebox.showerror('卡带加载失败', str(error), parent=window)
        def eject():
            pause(); self.eject(); self.on_change(); refresh()
        bar = ttk.Frame(window); bar.pack(padx=4, pady=4)
        tk.Button(bar, text='加载 ROM', command=insert).pack(side='left')
        tk.Button(bar, text='取出', command=eject).pack(side='left', padx=3)
        refresh()
        return window
