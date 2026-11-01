"""Standalone Tk view for CF media and non-destructive image editing."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from .cf_editor import CFImageEditor, create_blank_image, SECTOR

def open_cf_window(root, device, pause):
    editor = CFImageEditor(device)
    window = tk.Toplevel(root)
    window.title(getattr(device, 'name', 'CF 卡'))
    status = ttk.Label(window, padding=3, wraplength=440)
    status.pack(fill='x')
    toolbar = ttk.Frame(window, padding=3); toolbar.pack(fill='x')
    row = ttk.Frame(window, padding=3); row.pack(fill='x')
    ttk.Label(row, text='扇区 LBA（十进制或 0x 十六进制）').pack(side='left')
    address = tk.StringVar(value='0')
    ttk.Entry(row, textvariable=address, width=12).pack(side='left', padx=4)
    body = ttk.Frame(window); body.pack(fill='both', expand=True, padx=3, pady=3)
    content = tk.Text(body, width=50, height=10, font=('Consolas', 10), undo=True)
    scroll = ttk.Scrollbar(body, orient='vertical', command=content.yview)
    content.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y'); content.pack(fill='both', expand=True)
    footer = ttk.Label(window, text='编辑后先暂存扇区，再另存为新镜像。', padding=3)
    footer.pack(anchor='w')
    current = {'number': None}

    def display_status():
        if device.image is None:
            status.config(text='未加载镜像')
        else:
            status.config(text=f'镜像: {device.image}  |  {device.sectors} 扇区  |  '
                               f'{"只读" if device.readonly else "模拟机可写"}  |  暂存 {len(editor.changes)} 个扇区')

    def warn_unsaved():
        if (editor.changes or content.edit_modified()) and not messagebox.askyesno(
                '未保存的编辑', '切换镜像会丢弃尚未另存的编辑，继续吗？', parent=window):
            return False
        return True

    def show_sector():
        if content.edit_modified() and not messagebox.askyesno(
                '未暂存的编辑', '当前文本尚未暂存，放弃并切换扇区吗？', parent=window):
            return
        try:
            number = int(address.get(), 0)
            data = editor.sector(number)
        except (ValueError, OSError) as error:
            messagebox.showerror('读取失败', str(error), parent=window); return
        content.delete('1.0', 'end')
        content.insert('1.0', '\n'.join(' '.join(f'{b:02X}' for b in data[i:i + 16]) for i in range(0, SECTOR, 16)))
        content.edit_modified(False)
        current['number'] = number
        display_status()

    def stage():
        pause()
        try:
            if current['number'] is None: raise ValueError('请先读取一个扇区')
            editor.edit(current['number'], bytes.fromhex(content.get('1.0', 'end')))
        except (ValueError, OSError) as error:
            messagebox.showerror('暂存失败', str(error), parent=window); return False
        content.edit_modified(False); display_status(); return True

    def load():
        pause()
        if not warn_unsaved(): return
        path = filedialog.askopenfilename(parent=window, title='加载 CF 原始镜像')
        if not path: return
        try: editor.mount(path, readonly=True)
        except (OSError, ValueError) as error:
            messagebox.showerror('加载失败', str(error), parent=window); return
        content.edit_modified(False); address.set('0'); show_sector()

    def create():
        pause()
        if not warn_unsaved(): return
        sectors = simpledialog.askinteger('新建 CF 镜像', '扇区数量（每扇区 512 字节）:',
                                          initialvalue=65536, minvalue=1, maxvalue=0x10000000, parent=window)
        if sectors is None: return
        path = filedialog.asksaveasfilename(parent=window, title='新建镜像', defaultextension='.img', confirmoverwrite=False)
        if not path: return
        try:
            create_blank_image(path, sectors)
            editor.mount(path, readonly=True)
        except (OSError, ValueError) as error:
            messagebox.showerror('新建失败', str(error), parent=window); return
        content.edit_modified(False); address.set('0'); show_sector()

    def import_file():
        pause()
        path = filedialog.askopenfilename(parent=window, title='选择待导入的二进制文件')
        if not path: return
        offset = simpledialog.askinteger('导入', '写入镜像的字节偏移（十进制）:', minvalue=0, parent=window)
        if offset is None: return
        if content.edit_modified() and not stage(): return
        try: editor.import_bytes(offset, Path(path).read_bytes())
        except (OSError, ValueError) as error:
            messagebox.showerror('导入失败', str(error), parent=window); return
        if current['number'] is not None: show_sector()
        display_status()

    def save_as():
        pause()
        if content.edit_modified() and not stage(): return
        path = filedialog.asksaveasfilename(parent=window, title='另存为新镜像', defaultextension='.img', confirmoverwrite=False)
        if not path: return
        try: editor.export(path)
        except (OSError, ValueError) as error:
            messagebox.showerror('另存失败', str(error), parent=window); return
        if messagebox.askyesno('已保存', '已保存新镜像。是否立即加载新镜像？', parent=window):
            editor.mount(path, readonly=True)
            if current['number'] is not None: show_sector()
        display_status()

    def eject():
        pause()
        if not warn_unsaved(): return
        editor.eject(); current['number'] = None
        content.delete('1.0', 'end'); content.edit_modified(False); display_status()

    def toggle_write():
        pause()
        if device.image is None:
            messagebox.showerror('未加载镜像', '请先加载镜像。', parent=window); return
        readonly = not device.readonly
        if not readonly and not messagebox.askyesno(
                '启用模拟机写入', '模拟机写入将直接修改当前镜像。是否继续？', parent=window):
            return
        try:
            # Do not discard staged editor changes when changing write mode.
            device.mount(device.image, readonly)
        except (OSError, ValueError) as error:
            messagebox.showerror('设置失败', str(error), parent=window); return
        display_status()

    def close():
        if warn_unsaved(): window.destroy()

    for label, action in (('加载', load), ('新建', create), ('导入固件', import_file),
                          ('暂存扇区', stage), ('另存为', save_as), ('切换写入', toggle_write), ('弹出', eject)):
        tk.Button(toolbar, text=label, command=action).pack(side='left', padx=2)
    tk.Button(row, text='读取', command=show_sector).pack(side='left')
    window.protocol('WM_DELETE_WINDOW', close)
    window.can_close = warn_unsaved
    display_status()
    if device.image is not None: show_sector()
    return window
