"""Unified CPU-address-space RAM/ROM monitor."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from platform_support.i18n import translate, translate_error
from .memory_model import snapshot, write_bytes, prepare_import, check_range

def number(value):
    return int(value.strip(), 16)

def open_memory_window(root, machine, pause, language=lambda: 'zh'):
    def tr(text, **kwargs): return translate(text, language(), **kwargs)
    window = tk.Toplevel(root); window.title(tr('内存监视器'))
    toolbar = ttk.Frame(window, padding=3); toolbar.pack(fill='x')
    start_var = tk.StringVar(value='0000'); length_var = tk.StringVar(value='0100')
    start_label = ttk.Label(toolbar, text=tr('起始地址（十六进制）')); start_label.pack(side='left')
    ttk.Entry(toolbar, textvariable=start_var, width=7).pack(side='left', padx=4)
    length_label = ttk.Label(toolbar, text=tr('长度（十六进制）')); length_label.pack(side='left')
    ttk.Entry(toolbar, textvariable=length_var, width=7).pack(side='left', padx=4)
    allow_rom = tk.BooleanVar(value=False)
    rom_check = ttk.Checkbutton(toolbar, text=tr('允许修改 ROM'), variable=allow_rom); rom_check.pack(side='left', padx=8)
    buttons = ttk.Frame(window, padding=(3, 0)); buttons.pack(fill='x')
    status = ttk.Label(window, text=tr('RAM 蓝　ROM 黄　未映射 灰；双击修改'), padding=3); status.pack(anchor='w')
    body = ttk.Frame(window); body.pack(fill='both', expand=True, padx=3, pady=3)
    view = tk.Text(body, width=57, height=10, font=('Consolas', 10), wrap='none', state='disabled')
    scroll = ttk.Scrollbar(body, orient='vertical', command=view.yview)
    view.configure(yscrollcommand=scroll.set); scroll.pack(side='right', fill='y'); view.pack(fill='both', expand=True)
    view.tag_configure('ram', background='#dceeff'); view.tag_configure('rom', background='#fff0bd')
    view.tag_configure('unmapped', background='#e8e8e8')
    active = {'start': 0, 'length': 256, 'previous': None}
    def refresh(force=False):
        if not window.winfo_exists(): return
        try: data = snapshot(machine, active['start'], active['length'])
        except ValueError: return
        if force or data != active['previous']:
            position = view.yview()[0]
            previous = active['previous']
            changed = [] if previous is None or len(previous) != len(data) or force else [
                index for index, (old, new) in enumerate(zip(previous, data)) if old != new]
            view.configure(state='normal')
            if previous is not None and not force and len(previous) == len(data) and len(changed) <= 512:
                for index in changed:
                    loc = f'{index // 16 + 1}.{6 + (index % 16) * 3}'
                    value, kind = data[index]
                    view.delete(loc, f'{loc}+2c'); view.insert(loc, f'{value:02X}', kind)
            else:
                view.delete('1.0', 'end')
                for index in range(0, len(data), 16):
                    parts = [f"{active['start'] + index:04X}: ", '']
                    for value, kind in data[index:index + 16]: parts.extend((f'{value:02X}', kind, ' ', ''))
                    parts.extend(('\n', ''))
                    view.insert('end', *parts)
            view.configure(state='disabled'); view.yview_moveto(position)
            active['previous'] = data
    def apply_range():
        try:
            start, length = number(start_var.get()), number(length_var.get()); check_range(start, length)
            active.update(start=start, length=length); refresh(True)
        except ValueError as error: messagebox.showerror(tr('范围错误'), translate_error(error, language()), parent=window)
    def edit(event):
        line, col = map(int, view.index(f'@{event.x},{event.y}').split('.'))
        byte = (col - 6) // 3
        if col < 6 or byte not in range(16) or (col - 6) % 3 == 2: return
        offset = (line - 1) * 16 + byte
        if offset >= active['length']: return
        address = active['start'] + offset
        pause()
        value = simpledialog.askstring(tr('修改内存'), tr('地址 {address:04X}，输入两位十六进制数：', address=address), parent=window)
        if value is None: return
        try:
            if len(value.strip()) != 2: raise ValueError('请输入两位十六进制数')
            write_bytes(machine, address, bytes([number(value)]), allow_rom.get()); refresh(True)
        except (ValueError, OverflowError) as error: messagebox.showerror(tr('修改失败'), translate_error(error, language()), parent=window)
    view.bind('<Double-Button-1>', edit)
    def export():
        path = filedialog.asksaveasfilename(parent=window, defaultextension='.bin', filetypes=[(tr('二进制文件'), '*.bin'), (tr('所有文件'), '*')])
        if not path: return
        try: Path(path).write_bytes(bytes(value for value, _ in snapshot(machine, active['start'], active['length'])))
        except (OSError, ValueError) as error: messagebox.showerror(tr('导出失败'), translate_error(error, language()), parent=window)
    def import_file():
        pause()
        path = filedialog.askopenfilename(parent=window, filetypes=[(tr('二进制文件'), '*.bin'), (tr('所有文件'), '*')])
        if not path: return
        try: raw = Path(path).read_bytes()
        except OSError as error: messagebox.showerror(tr('读取失败'), translate_error(error, language()), parent=window); return
        dialog = tk.Toplevel(window); dialog.title(tr('导入二进制')); dialog.transient(window); dialog.grab_set()
        address = tk.StringVar(value=f"{active['start']:04X}")
        length = tk.StringVar(value='')
        fill = tk.StringVar(value='00')
        for row, (label, var) in enumerate((('起始地址（十六进制）', address), ('长度（十六进制，留空自动）', length))):
            ttk.Label(dialog, text=tr(label)).grid(row=row, column=0, padx=8, pady=5, sticky='w')
            ttk.Entry(dialog, textvariable=var, width=12).grid(row=row, column=1, padx=8, pady=5)
        ttk.Label(dialog, text=tr('文件长度：{length} 字节；长度较短时截取，较长时填充', length=len(raw))).grid(row=2, column=0, columnspan=2, padx=8)
        ttk.Label(dialog, text=tr('填充值')).grid(row=3, column=0, sticky='w', padx=8)
        ttk.Combobox(dialog, textvariable=fill, values=('00', 'FF'), state='readonly', width=9).grid(row=3, column=1, padx=8, pady=5)
        def apply():
            try:
                payload = prepare_import(raw, number(length.get()) if length.get().strip() else None, number(fill.get()))
                write_bytes(machine, number(address.get()), payload, allow_rom.get())
            except (ValueError, OverflowError) as error:
                messagebox.showerror(tr('导入失败'), translate_error(error, language()), parent=dialog); return
            dialog.destroy(); refresh(True)
        tk.Button(dialog, text=tr('导入'), command=apply).grid(row=4, column=0, columnspan=2, pady=8)
    local_buttons = []
    for title, command in (('应用范围', apply_range), ('导入 BIN', import_file), ('导出 BIN', export)):
        button = tk.Button(buttons, text=tr(title), command=command); button.pack(side='left', padx=3)
        local_buttons.append((button, title))
    def set_language():
        window.title(tr('内存监视器'))
        start_label.config(text=tr('起始地址（十六进制）'))
        length_label.config(text=tr('长度（十六进制）'))
        rom_check.config(text=tr('允许修改 ROM'))
        status.config(text=tr('RAM 蓝　ROM 黄　未映射 灰；双击修改'))
        for button, title in local_buttons: button.config(text=tr(title))
        # Component windows have explicit tiled geometries.  When translated
        # labels need more room, grow this window after Tk recalculates their
        # requested sizes so the controls do not get clipped.
        def fit_controls():
            if not window.winfo_exists(): return
            width = max(window.winfo_width(), window.winfo_reqwidth())
            height = max(window.winfo_height(), window.winfo_reqheight())
            if (width, height) != (window.winfo_width(), window.winfo_height()):
                window.geometry(f'{width}x{height}')
        window.after_idle(fit_controls)
    window._set_language = set_language
    def periodic():
        if window.winfo_exists(): refresh(); window.after(500, periodic)
    periodic()
    return window
