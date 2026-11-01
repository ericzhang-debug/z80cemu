"""Tk front end. Simulation and all device callbacks run on the Tk thread."""
import time
import argparse
import math
from decimal import Decimal, InvalidOperation
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from machine_loader import load_machine
from platform_support.window_style import install_child_window_policy
from platform_support import i18n
from platform_support.about import APP_VERSION, show_about, show_third_party

def _ranges(values, width):
    values = sorted(set(values))
    if not values: return '—'
    ranges = []
    first = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            ranges.append(f'{first:0{width}X}' if first == previous else f'{first:0{width}X}–{previous:0{width}X}')
            first = value
        previous = value
    ranges.append(f'{first:0{width}X}' if first == previous else f'{first:0{width}X}–{previous:0{width}X}')
    return ', '.join(ranges)

def port_mapping_rows(machine, language='zh'):
    """Summarize actual mappings, including ports that have never been accessed."""
    by_device = {}
    for address, device in machine.ports.items():
        key = id(device)
        if key not in by_device: by_device[key] = (device, [])
        by_device[key][1].append(address)
    result = []
    for device, addresses in by_device.values():
        low = {address & 255 for address in addresses}
        if len(addresses) == 256 * len(low):
            mapping = f'{_ranges(low, 2)}{i18n.translate("（低 8 位；高 8 位任意）", language)}'
        else:
            mapping = _ranges(addresses, 4)
        result.append((device.name, mapping))
    return result

def tile_rectangles(count, screen_width, screen_height, preferred_sizes=None):
    """Return non-overlapping rectangles for a set of component windows."""
    if count <= 0: return []
    width = max(1, screen_width)
    height = max(1, screen_height - 48)  # Leave room for the taskbar.
    if preferred_sizes is not None:
        if len(preferred_sizes) != count: raise ValueError('窗口数量与尺寸不一致')
        result = []
        x = y = row_height = 0
        for preferred_width, preferred_height in preferred_sizes:
            client_width = min(max(1, preferred_width), max(1, width - 16))
            client_height = min(max(1, preferred_height), max(1, height - 39))
            outer_width, outer_height = client_width + 16, client_height + 39
            if x and x + outer_width > width:
                y += row_height; x = row_height = 0
            if y + outer_height > height:
                result = []; break
            result.append((client_width, client_height, x, y))
            x += outer_width; row_height = max(row_height, outer_height)
        if result: return result
    columns = max(1, min(count, math.ceil(math.sqrt(count * width / height))))
    rows = math.ceil(count / columns)
    result = []
    for i in range(count):
        row, column = divmod(i, columns)
        left, right = column * width // columns, (column + 1) * width // columns
        top, bottom = row * height // rows, (row + 1) * height // rows
        # Window frames occupy screen space outside the client geometry.
        available_width, available_height = max(1, right - left - 16), max(1, bottom - top - 39)
        if preferred_sizes is not None:
            available_width = min(available_width, max(1, preferred_sizes[i][0]))
            available_height = min(available_height, max(1, preferred_sizes[i][1]))
        result.append((available_width, available_height, left, top))
    return result

class App:
    def __init__(self, root, path=None, loaded=None):
        self.root = root
        install_child_window_policy(root)
        self.active = True
        if path is None and loaded is None: raise ValueError('必须指定机器配置脚本')
        self.machine_path = Path(path) if path else Path('custom')
        self.machine, clock_hz = loaded or load_machine(self.machine_path)
        self.language = i18n.load_language()
        self._localized_windows = []
        self._language_var = tk.StringVar(root, value=self.language)
        self.clock_hz = clock_hz
        self.component_windows = {}
        self._tile_pending = False
        self.running = False
        self.actual_hz = 0.0
        self._speed_time = time.monotonic()
        self._speed_cycles = self.machine.cycles
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.last = time.monotonic()
        self.credit = 0.0
        root.title(f'{self.tr("Z80模拟")}-{self.machine_path.stem}')
        root.geometry('520x360'); root.minsize(420, 280)
        style = ttk.Style(root)
        style.configure('Status.TLabel', font=('Consolas', 11), padding=8)
        self._build_menu()
        groups = ttk.Frame(root); groups.pack(fill='x', padx=6, pady=(0, 4))
        self.control = ttk.LabelFrame(groups, text=self.tr('运行控制'), padding=4); self.control.pack(side='left', fill='both')
        self.run_button = tk.Button(self.control, text=self.tr('开始'), command=self.toggle_run)
        self.run_button.pack(side='left', padx=2)
        self.status = tk.Label(self.control, anchor='w'); self.status.pack(side='left', padx=(6, 3))
        self.frequency_label = tk.Label(self.control, anchor='w'); self.frequency_label.pack(side='left', padx=3)
        self.content = ttk.LabelFrame(root, text=self.tr('机器组件  ·  双击打开'), padding=4)
        self.content.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        self.list = tk.Listbox(self.content, height=8, width=45, font=('Microsoft YaHei UI', 10))
        self.list.pack(fill='both', expand=True)
        for component in self.machine.components: self.list.insert('end', '  ' + component.name)
        self.list.bind('<Double-Button-1>', self.open_component)
        self.refresh()
        root.after(20, self.loop)
        for component in self.machine.components:
            if callable(getattr(component, 'bind_ui', None)):
                component.bind_ui(root, self.pause)
        self._ui_tick_hooks = [component.ui_tick for component in self.machine.components
                               if callable(getattr(component, 'ui_tick', None))]
        requested = getattr(self.machine, 'auto_open_windows', None)
        for component in self.machine.components:
            if requested is None or component.name in requested:
                self.show_component(component)

    def tr(self, text, **kwargs):
        return i18n.translate(text, self.language, **kwargs)

    def _build_menu(self):
        old = getattr(self, 'menu', None)
        menu = tk.Menu(self.root)
        machine_menu = tk.Menu(menu, tearoff=False)
        machine_menu.add_command(label=self.tr('打开机器配置…'), command=self.open_machine)
        machine_menu.add_separator(); machine_menu.add_command(label=self.tr('退出'), command=self.close)
        menu.add_cascade(label=self.tr('机器'), menu=machine_menu)
        run_menu = tk.Menu(menu, tearoff=False)
        run_menu.add_command(label=self.tr('单步'), command=self.step)
        run_menu.add_command(label=self.tr('复位'), command=self.reset)
        run_menu.add_separator()
        run_menu.add_command(label=self.tr('设置频率（{clock} MHz）…', clock=f'{self.clock_hz / 1000000:g}'), command=self.set_clock)
        self.run_menu = run_menu
        menu.add_cascade(label=self.tr('运行'), menu=run_menu)
        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(label=self.tr('CPU 寄存器'), command=lambda: self.show_component(self.machine.cpu))
        view_menu.add_command(label=self.tr('I/O 端口'), command=self.io_window)
        menu.add_cascade(label=self.tr('查看'), menu=view_menu)
        language_menu = tk.Menu(menu, tearoff=False)
        for label, value in (('中文', 'zh'), ('English', 'en')):
            language_menu.add_radiobutton(label=label, variable=self._language_var, value=value,
                                          command=lambda lang=value: self.set_language(lang))
        menu.add_cascade(label=self.tr('设置语言'), menu=language_menu)
        menu.add_command(label=self.tr('第三方程序使用'), command=self.show_third_party)
        menu.add_command(label=self.tr('关于'), command=self.show_about)
        self.root.configure(menu=menu)
        self.menu = menu
        if old is not None: old.destroy()

    def set_language(self, language):
        try:
            i18n.save_language(language)
        except (OSError, ValueError) as error:
            self._language_var.set(self.language)
            messagebox.showerror(self.tr('语言设置错误'), self.tr('无法保存语言设置：{error}', error=error), parent=self.root)
            return
        self.language = language
        self._language_var.set(language)
        self._build_menu()
        self.root.title(f'{self.tr("Z80模拟")}-{self.machine_path.stem}')
        self.control.config(text=self.tr('运行控制'))
        self.content.config(text=self.tr('机器组件  ·  双击打开'))
        self.refresh()
        self._localized_windows = [window for window in self._localized_windows if window.winfo_exists()]
        for window in self._localized_windows: window._set_language()

    def show_about(self):
        return show_about(self.root, self.language)

    def show_third_party(self):
        return show_third_party(self.root, self.language)

    def start(self):
        for component in self.machine.components:
            if hasattr(component, 'cpu_hz'): component.cpu_hz = self.clock_hz
        self.last = time.monotonic(); self.credit = 0; self.running = True
        self.actual_hz = 0.0
        self._speed_time, self._speed_cycles = self.last, self.machine.cycles
        self.schedule_tiling()
        self.refresh()

    def pause(self):
        self.running = False
        self.actual_hz = 0.0
        self.refresh()

    def toggle_run(self):
        if self.running: self.pause()
        else: self.start()

    def set_clock(self):
        value = simpledialog.askstring(self.tr('系统频率'), self.tr('输入频率（MHz）：'), initialvalue=f'{self.clock_hz / 1000000:g}', parent=self.root)
        if value is None: return
        try:
            hz = Decimal(value.strip()) * 1000000
            if not hz.is_finite() or hz <= 0 or hz != hz.to_integral_value(): raise ValueError()
            self.clock_hz = int(hz)
        except (InvalidOperation, ValueError, OverflowError):
            messagebox.showerror(self.tr('频率错误'), self.tr('请输入大于 0 且精确到 1 Hz 的频率（MHz）。'), parent=self.root); return
        for component in self.machine.components:
            if hasattr(component, 'cpu_hz'): component.cpu_hz = self.clock_hz
        self.credit = 0; self.last = time.monotonic()
        self.actual_hz = 0.0
        self._speed_time, self._speed_cycles = self.last, self.machine.cycles
        self.run_menu.entryconfigure('end', label=self.tr('设置频率（{clock} MHz）…', clock=f'{self.clock_hz / 1000000:g}'))
    def close(self):
        if not self.can_close_views(): return
        self.active = False
        self.pause()
        self._close_components_ui()
        self.root.destroy()

    def _close_components_ui(self):
        for component in self.machine.components:
            close = getattr(component, 'close_ui', None)
            if callable(close): close()
    def can_close_views(self):
        return all(not hasattr(widget, 'can_close') or widget.can_close()
                   for widget in self.root.winfo_children() if widget.winfo_exists())
    def open_machine(self):
        self.pause()
        path = filedialog.askopenfilename(parent=self.root, title=self.tr('选择机器组装脚本'), filetypes=[(self.tr('Python 机器脚本'), '*.py')])
        if not path: return
        if not self.can_close_views(): return
        try: loaded = load_machine(path)
        except Exception as error:
            messagebox.showerror(self.tr('机器加载失败'), i18n.translate_error(error, self.language), parent=self.root); return
        self.active = False
        self._close_components_ui()
        for widget in self.root.winfo_children(): widget.destroy()
        App(self.root, path, loaded)
    def step(self):
        self.pause(); self.machine.step(); self.refresh()
    def reset(self):
        self.pause(); self.machine.reset()
        for component in self.machine.components:
            if callable(getattr(component, 'clear_output', None)): component.clear_output()
        self.refresh()
    def refresh(self):
        self.status.config(text=self.tr('运行中' if self.running else '暂停'), fg='green' if self.running else 'red')
        self.frequency_label.config(text=self.tr('实际频率：{frequency:.3f} MHz', frequency=self.actual_hz / 1000000))
        self.run_button.config(text=self.tr('暂停按钮' if self.running else '开始') if self.language == 'en' else ('暂停' if self.running else '开始'))

    def sample_speed(self, now):
        elapsed = now - self._speed_time
        if self.running and elapsed >= 0.5:
            self.actual_hz = max(0, self.machine.cycles - self._speed_cycles) / elapsed
            self._speed_time, self._speed_cycles = now, self.machine.cycles
    def loop(self):
        if not self.active: return
        now = time.monotonic()
        if self.running:
            try:
                hz = self.clock_hz
                self.credit = min(self.credit + (now - self.last) * hz, hz * 0.1)
                deadline = time.monotonic() + 0.012
                while self.credit > 0 and time.monotonic() < deadline:
                    budget = min(max(1, int(self.credit)), 2048)
                    self.credit -= self.machine.run_for(budget) if callable(getattr(self.machine, 'run_for', None)) else self.machine.step()
            except Exception as exc:
                self.pause(); messagebox.showerror(self.tr('运行错误'), i18n.translate_error(exc, self.language), parent=self.root)
        self.last = now
        for callback in self._ui_tick_hooks: callback()
        self.sample_speed(time.monotonic())
        self.refresh()
        if self.running:
            # A continuous stream of zero-delay timers starves Tk idle work,
            # including repainting child windows. Let pending input and redraws
            # run before scheduling the next simulation batch, without adding
            # a fixed Windows timer delay to every batch.
            self.root.after_idle(self._schedule_running_loop)
        else:
            self.root.after(50, self.loop)

    def _schedule_running_loop(self):
        if self.active:
            self.root.after(0, self.loop)

    def cpu_window(self):
        window = tk.Toplevel(self.root); window.title(self.machine.cpu.name + self.tr(' 寄存器'))
        window._set_language = lambda: window.title(self.machine.cpu.name + self.tr(' 寄存器'))
        self._localized_windows.append(window)
        label = ttk.Label(window, font=('Consolas', 10), padding=4); label.pack()
        def update():
            if not window.winfo_exists(): return
            c = self.machine.cpu.cpu
            fields = ('pc','sp','af','bc','de','hl','af','bc_','de_','hl_','i','r','im','iff1','iff2')
            values = [f'{n.upper():5} {getattr(c,n):04X}' for n in fields]
            values.extend([f'IX    {c.ix_iy[0]:04X}', f'IY    {c.ix_iy[1]:04X}'])
            label.config(text='\n'.join(values)); window.after(150, update)
        update()
        return window

    def io_window(self):
        window = tk.Toplevel(self.root); window.title(self.tr('I/O 端口监视')); window.geometry('760x520')
        tabs = ttk.Notebook(window); tabs.pack(fill='both', expand=True, padx=8, pady=8)
        mappings = ttk.Frame(tabs, padding=8); tabs.add(mappings, text=self.tr('器件端口映射'))
        mapping_label = ttk.Label(mappings, text=self.tr('显示已连接器件及其端口，包括尚未访问的端口。')); mapping_label.pack(anchor='w', pady=(0, 6))
        mapping_text = tk.Text(mappings, height=18, wrap='word')
        mapping_text.pack(fill='both', expand=True)
        live = ttk.Frame(tabs, padding=8); tabs.add(live, text=self.tr('实时访问与查询'))
        bar = ttk.Frame(live); bar.pack(fill='x', pady=(0, 6))
        query_label = ttk.Label(bar, text=self.tr('端口（十六进制，留空显示已访问端口）')); query_label.pack(side='left')
        query = tk.StringVar(); ttk.Entry(bar, textvariable=query, width=9).pack(side='left', padx=6)
        full_address = tk.BooleanVar(value=False)
        full_check = ttk.Checkbutton(bar, text=self.tr('显示完整 16 位地址'), variable=full_address); full_check.pack(side='left')
        note = ttk.Label(live); note.pack(anchor='w')
        table = ttk.Treeview(live, columns=('device', 'action', 'value', 'count'), show='tree headings')
        for col, title, width in (('#0', '端口', 75), ('device', '对应器件', 220), ('action', '最近操作', 90), ('value', '数值', 80), ('count', '访问次数', 100)):
            table.heading(col, text=self.tr(title)); table.column(col, width=width, stretch=(col == 'device'))
        scroll = ttk.Scrollbar(live, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set); scroll.pack(side='right', fill='y'); table.pack(fill='both', expand=True)
        low_devices = {}
        for port, device in self.machine.ports.items():
            names = low_devices.setdefault(port & 255, set())
            names.add(device.name)
        def update():
            if not window.winfo_exists(): return
            full = full_address.get()
            maximum = 0xffff if full else 0xff
            width = 4 if full else 2
            try:
                selected = int(query.get().strip(), 16) if query.get().strip() else None
                if selected is not None and not 0 <= selected <= maximum: raise ValueError()
                note.config(text='' if full else self.tr('按低 8 位汇总；高 8 位不同的访问计入同一端口。'))
            except ValueError:
                selected = -1; note.config(text=self.tr('请输入 00 到 {maximum} 之间的十六进制端口。', maximum=f'{maximum:0{width}X}'))
            history = self.machine.io_history if full else self.machine.io_low_history
            counts = self.machine.io_counts if full else self.machine.io_low_counts
            addresses = sorted(history) if selected is None else ([] if selected == -1 else [selected])
            wanted = {f'{address:0{width}X}' for address in addresses}
            for item in table.get_children():
                if item not in wanted: table.delete(item)
            for addr in addresses:
                if full:
                    device = self.machine.ports.get(addr)
                    names = device.name if device else self.tr('未映射')
                    action, value = history.get(addr, ('—', None))
                else:
                    names = '、'.join(sorted(low_devices.get(addr, ()))) or self.tr('未映射')
                    action, value, _ = history.get(addr, ('—', None, None))
                values = (names, self.tr(action), f'{value:02X}' if value is not None else '—', counts.get(addr, 0))
                iid = f'{addr:0{width}X}'
                if table.exists(iid): table.item(iid, values=values)
                else: table.insert('', 'end', iid=iid, text=iid, values=values)
            window.after(300, update)
        def set_language():
            window.title(self.tr('I/O 端口监视'))
            tabs.tab(mappings, text=self.tr('器件端口映射'))
            tabs.tab(live, text=self.tr('实时访问与查询'))
            mapping_label.config(text=self.tr('显示已连接器件及其端口，包括尚未访问的端口。'))
            query_label.config(text=self.tr('端口（十六进制，留空显示已访问端口）'))
            full_check.config(text=self.tr('显示完整 16 位地址'))
            for col, title in (('#0', '端口'), ('device', '对应器件'), ('action', '最近操作'), ('value', '数值'), ('count', '访问次数')):
                table.heading(col, text=self.tr(title))
            mapping_text.configure(state='normal'); mapping_text.delete('1.0', 'end')
            for name, ports in port_mapping_rows(self.machine, self.language):
                mapping_text.insert('end', f'{name}\n  {ports}\n\n')
            mapping_text.configure(state='disabled')
        window._set_language = set_language
        self._localized_windows.append(window)
        set_language()
        update()
        return window

    def open_component(self, _event=None):
        selection = self.list.curselection()
        if not selection: return
        self.show_component(self.machine.components[selection[0]])

    def show_component(self, device):
        key = 'memory' if any(device is item for item in self.machine.memory) else id(device)
        previous = self.component_windows.get(key)
        if previous is not None and previous.winfo_exists():
            previous.lift(); return previous
        window = self._create_component_window(device)
        if window is not None:
            self.component_windows[key] = window
            resizable = bool(getattr(device, 'gui_resizable', False))
            window.resizable(resizable, resizable)
            self._bind_component_input(device, window)
            self.schedule_tiling()
        return window

    def schedule_tiling(self):
        if not self._tile_pending:
            self._tile_pending = True
            self.root.after_idle(self.tile_component_windows)

    def tile_component_windows(self):
        self._tile_pending = False
        if not self.active: return
        windows = [window for window in self.component_windows.values() if window.winfo_exists()]
        self.root.update_idletasks()
        preferred = [getattr(window, 'tile_preferred', (window.winfo_reqwidth(), window.winfo_reqheight())) for window in windows]
        rectangles = tile_rectangles(len(windows), self.root.winfo_screenwidth(), self.root.winfo_screenheight(), preferred)
        for window, (width, height, x, y) in zip(windows, rectangles):
            window.geometry(f'{width}x{height}+{x}+{y}')

    def _bind_component_input(self, device, window):
        keyboards = [keyboard for keyboard, target in getattr(self.machine, 'input_bindings', ()) if target is device]
        if not keyboards: return
        pressed = {}
        def press(event):
            identity = event.keycode or event.keysym
            keysym = pressed.setdefault(identity, event.keysym)
            for keyboard in keyboards: keyboard.key_event(keysym, True)
        def release(event):
            identity = event.keycode or event.keysym
            keysym = pressed.pop(identity, event.keysym)
            for keyboard in keyboards: keyboard.key_event(keysym, False)
        def clear(_event):
            for key in tuple(pressed.values()):
                for keyboard in keyboards: keyboard.key_event(key, False)
            pressed.clear()
        window.bind('<KeyPress>', press, add='+')
        window.bind('<KeyRelease>', release, add='+')
        window.bind('<FocusOut>', clear, add='+')
        window.bind('<Destroy>', clear, add='+')

    def _create_component_window(self, device):
        if device is self.machine.cpu: return self.cpu_window()
        if any(device is memory for memory in self.machine.memory):
            from ui.memory_window import open_memory_window
            window = open_memory_window(self.root, self.machine, self.pause, lambda: self.language)
            self._localized_windows.append(window)
            return window
        if callable(getattr(device, 'open_gui', None)):
            return device.open_gui(self.root, self.pause)
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Z80 模拟平台')
    parser.add_argument('--machine', type=Path, required=True, help='机器组装脚本路径')
    args = parser.parse_args()
    root = tk.Tk()
    try: App(root, args.machine)
    except Exception as exc:
        language = i18n.load_language()
        messagebox.showerror(i18n.translate('启动失败', language), i18n.translate_error(exc, language)); root.destroy()
    else: root.mainloop()
