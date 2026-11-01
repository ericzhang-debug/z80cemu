"""Views used by optional expansion components."""
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque

def video_window(root, device, pause):
    window = tk.Toplevel(root); window.title(device.name + ' 视频')
    window.geometry('560x450'); window.minsize(270, 230)
    window.tile_preferred = (560, 450)
    state = ttk.Label(window, text='等待程序启用显卡', padding=(3, 1)); state.pack(anchor='w')
    label = ttk.Label(window, anchor='center'); label.pack(padx=2, pady=2, fill='both', expand=True)
    label.bind('<Button-1>', lambda _event: window.focus_set())
    rendered = {'revision': None, 'scale': None}
    # Translate an entire color-index plane at once instead of converting
    # every pixel in Python on each frame.
    color_tables = [bytes([color[channel] for color in device.palette]
                          + [0] * (256 - len(device.palette)))
                    for channel in range(3)]
    def update():
        if not window.winfo_exists(): return
        state.config(text='视频输出已启用' if device.registers[1] & 0x40 else '显卡未启用（等待程序输出）')
        scale = max(1, min(label.winfo_width() // 256, label.winfo_height() // 192))
        revision = getattr(device, 'visual_revision', None)
        if revision is None or rendered['revision'] != revision or rendered['scale'] != scale:
            pixels = device.render()
            indices = bytes(pixels)
            rgb = bytearray(len(indices) * 3)
            for channel, table in enumerate(color_tables):
                rgb[channel::3] = indices.translate(table)
            raw = b'P6\n256 192\n255\n' + rgb
            label.image = tk.PhotoImage(data=raw, format='PPM')
            if scale > 1: label.image = label.image.zoom(scale)
            label.configure(image=label.image)
            rendered.update(revision=revision, scale=scale)
        window.after(100, update)
    update()
    return window

def joypad_window(root, device, pause):
    window = tk.Toplevel(root); window.title(device.name)
    for player in (1, 2):
        frame = ttk.LabelFrame(window, text=f'玩家 {player}', padding=2); frame.pack(side='left', padx=2, pady=2)
        frame.grid_columnconfigure(3, minsize=8)
        buttons = (('上', 'up', 0, 1), ('左', 'left', 1, 0),
                   ('右', 'right', 1, 2), ('下', 'down', 2, 1),
                   ('1', 'button1', 1, 4), ('2', 'button2', 1, 5))
        for label, key, row, column in buttons:
            button = tk.Button(frame, text=label, width=2, padx=0, pady=0)
            button.grid(row=row, column=column, padx=0, pady=0)
            button.bind('<ButtonPress-1>', lambda event, p=player, k=key: device.set_button(p, k, True))
            button.bind('<ButtonRelease-1>', lambda event, p=player, k=key: device.set_button(p, k, False))
    return window

def serial_window(root, device, pause):
    window = tk.Toplevel(root); window.title(device.name + ' 终端')
    window.geometry('700x420'); window.minsize(360, 220)
    window.tile_preferred = (700, 420)
    bar = ttk.Frame(window, padding=4); bar.pack(fill='x')
    ttk.Label(bar, text='波特率').pack(side='left')
    baud = tk.StringVar(value=str(device.baud))
    ttk.Combobox(bar, textvariable=baud, width=9, values=('300','1200','2400','4800','9600','19200','38400','57600','115200')).pack(side='left')
    def set_baud():
        try:
            value = int(baud.get())
            if value <= 0: raise ValueError()
            device.baud = value
        except ValueError: messagebox.showerror('波特率错误', '请输入正整数', parent=window)
    tk.Button(bar, text='设置', command=set_baud).pack(side='left')
    tk.Button(bar, text='清空', command=device.clear_output).pack(side='left', padx=4)
    ttk.Label(window, text='点击终端输入，回显由模拟机程序产生。').pack(anchor='w', padx=5)
    text = tk.Text(window, width=80, height=20, wrap='char', state='disabled'); text.pack(fill='both', expand=True)
    if not hasattr(device, '_terminal_pending'):
        device._terminal_pending = deque()
        device._terminal_sending = False
    def enqueue(data):
        device._terminal_pending.extend(data)
        if device._terminal_sending: return
        device._terminal_sending = True
        def send_next():
            if not getattr(device, '_ui_active', True):
                device._terminal_sending = False; return
            if device._terminal_pending:
                device.send(bytes([device._terminal_pending.popleft()]))
                root.after(30, send_next)
            else: device._terminal_sending = False
        send_next()
    def keypress(event):
        if event.state & 0x4:
            if event.keysym.lower() == 'c' and text.tag_ranges('sel'):
                return None
            if len(event.keysym) == 1 and event.keysym.isalpha():
                enqueue(bytes([ord(event.keysym.upper()) - ord('A') + 1]))
            return 'break'
        value = {'Return': b'\r', 'BackSpace': b'\x08', 'Tab': b'\t', 'Escape': b'\x1b'}.get(event.keysym)
        if value is None and event.char and event.char.isprintable():
            value = event.char.encode('ascii', errors='replace')
        if value: enqueue(value)
        return 'break'
    text.bind('<KeyPress>', keypress)
    text.bind('<Button-1>', lambda event: text.focus_set())
    cursor = 0
    generation = device.output_generation
    def update():
        nonlocal cursor, generation
        if not window.winfo_exists(): return
        if generation != device.output_generation:
            generation = device.output_generation; cursor = 0
            text.configure(state='normal'); text.delete('1.0', 'end'); text.configure(state='disabled')
        if len(device.output) > cursor:
            data = bytes(device.output[cursor:]); cursor += len(data)
            text.configure(state='normal')
            text.insert('end', data.decode('latin-1').replace('\r', ''))
            text.configure(state='disabled'); text.see('end')
        window.after(100, update)
    update()
    text.focus_set()
    return window

def device_window(root, device, pause):
    window = tk.Toplevel(root); window.title(device.name)
    label = ttk.Label(window, font=('Consolas', 10), padding=4); label.pack()
    def update():
        if not window.winfo_exists(): return
        lines = [device.name]
        if hasattr(device, 'core') and hasattr(device.core, 'channels'):
            for i, ch in enumerate(device.core.channels):
                lines.append(f'{i}: count={ch.count:03} control={ch.control:02X} running={int(ch.running)} IRQ={int(ch.pending)}')
        elif hasattr(device, 'ports'):
            for i, port in enumerate(device.ports):
                lines.append(f'{"AB"[i]}: mode={port.mode} input={port.inputs:02X} latch={port.latch:02X} ready={int(port.ready)} IRQ={int(port.pending)}')
        elif hasattr(device, 'value'):
            lines.append(f'LED  {device.value:08b}  ({device.value:02X})')
        else: lines.append('该部件没有状态窗口。')
        label.config(text='\n'.join(lines)); window.after(200, update)
    update()
    return window
