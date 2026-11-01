"""VTech/VZ printer interface with a persistent virtual paper spool.

Port 00h bit 0 reports busy; the firmware emits each byte once to 0Eh,
followed by 0Dh. We treat the 0Eh write as a byte transfer and retain the
0Dh write as interface state; electrical pulse timing is not modeled.
"""
from pathlib import Path


class VTechPrinter:
    batch_io_safe = True
    gui_resizable = True
    name = 'VTech 打印机'
    pins = {'D0-D7': 'bidirectional', '/IORQ': 'input', '/RD': 'input',
            '/WR': 'input', 'BUSY': 'input', '/STROBE': 'output'}

    def __init__(self):
        self.online = True
        self.raw = bytearray()
        self.output = self.raw
        self._pages = [['']]
        self._row = self._column = 0
        self.revision = 0
        self.reset()

    def reset(self):
        # Reset the interface, not paper already delivered to the printer.
        self.last_data = None
        self.last_write_port = None

    @property
    def busy(self): return not self.online

    @property
    def paper_text(self):
        return '\f'.join('\n'.join(page) for page in self._pages)

    def clear_paper(self):
        self.raw.clear()
        self._pages = [['']]
        self._row = self._column = 0
        self.revision += 1

    def read_port(self, address):
        if address & 0xff == 0:
            return 0xff if self.busy else 0xfe
        return 0xff

    def write_port(self, address, value):
        port, value = address & 0xff, value & 0xff
        if port not in (0x0d, 0x0e): return
        self.last_write_port, self.last_data = port, value
        if port != 0x0e or self.busy: return
        self.raw.append(value)
        self._write_paper(value)
        self.revision += 1

    def _write_paper(self, value):
        if value == 13:
            self._column = 0
        elif value == 10:
            self._row += 1
            page = self._pages[-1]
            if self._row == len(page): page.append('')
        elif value == 8:
            self._column = max(0, self._column - 1)
        elif value == 9:
            self._column = (self._column // 8 + 1) * 8
        elif value == 12:
            self._pages.append([''])
            self._row = self._column = 0
        elif 0x20 <= value <= 0x7e or value >= 0xa0:
            page = self._pages[-1]
            line = page[self._row]
            if self._column >= len(line): line += ' ' * (self._column + 1 - len(line))
            page[self._row] = line[:self._column] + chr(value) + line[self._column + 1:]
            self._column += 1

    def save_text(self, path):
        Path(path).write_text(self.paper_text, encoding='utf-8', newline='')

    def save_raw(self, path):
        Path(path).write_bytes(self.raw)

    def open_gui(self, root, pause):
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        window = tk.Toplevel(root)
        window.title(self.name)
        window.geometry('520x340')
        window.minsize(300, 180)
        window.tile_preferred = (520, 340)
        bar = ttk.Frame(window, padding=2); bar.pack(fill='x')
        online = tk.BooleanVar(window, self.online)
        def set_online(): self.online = online.get()
        ttk.Checkbutton(bar, text='联机', variable=online, command=set_online).pack(side='left')
        def clear(): self.clear_paper()
        def save(kind):
            path = filedialog.asksaveasfilename(parent=window, title='保存打印内容',
                defaultextension='.txt' if kind == 'text' else '.bin',
                filetypes=[('文本文件', '*.txt'), ('所有文件', '*.*')] if kind == 'text'
                          else [('二进制文件', '*.bin'), ('所有文件', '*.*')])
            if not path: return
            try:
                if kind == 'text': self.save_text(path)
                else: self.save_raw(path)
            except OSError as error:
                messagebox.showerror('保存失败', str(error), parent=window)
        tk.Button(bar, text='清空', command=clear).pack(side='left', padx=2)
        tk.Button(bar, text='保存文本', command=lambda: save('text')).pack(side='left', padx=2)
        tk.Button(bar, text='保存原始数据', command=lambda: save('raw')).pack(side='left', padx=2)
        frame = ttk.Frame(window); frame.pack(fill='both', expand=True, padx=2, pady=2)
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        scroll = ttk.Scrollbar(frame); scroll.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(frame, orient='horizontal'); horizontal.grid(row=1, column=0, sticky='ew')
        text = tk.Text(frame, width=56, height=14, wrap='none', state='disabled',
                       yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        text.grid(row=0, column=0, sticky='nsew')
        scroll.config(command=text.yview); horizontal.config(command=text.xview)
        displayed = -1
        def update():
            nonlocal displayed
            if not window.winfo_exists(): return
            if displayed != self.revision:
                displayed = self.revision
                following = text.yview()[1] >= 0.999
                text.config(state='normal'); text.delete('1.0', 'end')
                text.insert('1.0', self.paper_text.replace('\f', '\n──── 换页 ────\n'))
                text.config(state='disabled')
                if following: text.see('end')
            window.after(150, update)
        update()
        return window
