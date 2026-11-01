"""TP801 PROM sockets and the board's two-pulse programming control.

The caller connects the program-enable latch and CTC2 output. CPU writes
to the programming socket are intercepted while enabled; the caller holds
the CPU until the second CTC output pulse. Images are kept in memory until
the user explicitly exports them.
"""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


class PROMChip:
    """One address-mapped, electrically read-only, 2 KiB PROM socket."""
    pins = {'A0-A10': 'input', 'D0-D7': 'bidirectional', '/CE': 'input', '/OE': 'input', '/PGM': 'input'}

    def __init__(self, name, start, size=0x800):
        if not isinstance(start, int) or not isinstance(size, int) or size <= 0 or start < 0 or start + size > 0x10000:
            raise ValueError('PROM 地址范围无效')
        self.name, self.start, self.size = name, start, size
        self.readonly = True
        self.regions = [{'start': start, 'size': size, 'offset': 0}]
        self.data = bytearray([0xff]) * size
        self.mounted = False

    def contains(self, address): return self.start <= address < self.start + self.size
    def offset(self, address):
        if not self.contains(address): raise ValueError('地址不在 PROM 范围')
        return address - self.start
    def read(self, address): return self.data[self.offset(address)]
    def write(self, address, value): pass  # Normal CPU writes cannot program this chip.

    def mount(self, path):
        with Path(path).open('rb') as stream: data = stream.read(self.size + 1)
        if len(data) > self.size: raise ValueError(f'PROM 镜像不能超过 {self.size} 字节')
        self.data[:] = data.ljust(self.size, b'\xff')
        self.mounted = True
        return len(data)

    def export(self, path): Path(path).write_bytes(self.data)


class TP801PROMProgrammer:
    """Board-level controls, wired to two PROMChip instances by the machine."""
    pins = {'PROGRAM_ENABLE': 'input', 'CTC2': 'input', 'S2': 'output', 'S3': 'output'}
    name = 'TP801 PROM 编程器'

    def __init__(self, boot_chip, programming_chip):
        if boot_chip is programming_chip: raise ValueError('PROM 插槽需要两个不同器件')
        self.chips = (boot_chip, programming_chip)
        self.s2_prom_boot = False
        self.s3_program = False
        self.root = None
        self.pause = lambda: None
        self.read_byte = None
        self.reset()

    def reset(self):
        self.program_enable = False
        self.pending = None
        self.program_pulses = 0

    def set_enable(self, enabled):
        self.program_enable = bool(enabled)
        if not self.program_enable:
            self.pending = None
            self.program_pulses = 0

    @property
    def waiting(self): return self.pending is not None

    def intercept_write(self, address, value):
        """Return True if this CPU write entered the PROM programming cycle."""
        if not self.program_enable or not self.chips[1].contains(address): return False
        if self.pending is not None: raise RuntimeError('PROM 正等待编程脉冲')
        self.pending = (address, value & 0xff, self.s3_program)
        self.program_pulses = 0
        return True

    def on_ctc2_pulse(self, count=1):
        """Return True when a waiting CPU may resume; no write without PGM voltage."""
        if not isinstance(count, int) or count < 0: raise ValueError('脉冲数无效')
        if not self.program_enable or self.pending is None: return False
        self.program_pulses += count
        if self.program_pulses < 2: return False
        address, value, voltage = self.pending
        if voltage:
            chip = self.chips[1]
            chip.data[chip.offset(address)] &= value
            chip.mounted = True
        self.pending = None
        self.program_pulses = 0
        return True

    def pulse(self, count=1): return self.on_ctc2_pulse(count)

    def bind_ui(self, root, pause): self.root, self.pause = root, pause

    def request_program(self):
        if self.root is None: raise RuntimeError('请先将 PROM 编程器连接到平台界面')
        self.pause(); self.root.after_idle(self._program_from_ram)

    def _program_from_ram(self):
        try:
            if not self.s3_program: raise ValueError('请先将 S3 切换到 PGM 编程位置')
            if self.read_byte is None: raise ValueError('没有连接 RAM 数据源')
            digits = [self.read_byte(address) for address in range(0x2ff7, 0x2ffb)]
            if any(digit > 15 for digit in digits): raise ValueError('请先输入四位 PROM 编程字节数')
            count = sum(value << (12 - 4 * index) for index, value in enumerate(digits))
            chip = self.chips[1]
            if not 1 <= count <= chip.size: raise ValueError('PROM 编程长度超出范围')
            image = bytearray(chip.data)
            for index in range(count):
                value = self.read_byte(0x2000 + index)
                if image[index] & value != value: raise ValueError(f'PROM 地址 {chip.start + index:04X} 需要先擦除')
                image[index] = value
            path = filedialog.asksaveasfilename(parent=self.root, title='保存 PROM2 编程镜像', defaultextension='.bin')
            if not path: return
            Path(path).write_bytes(image)
            chip.data[:] = image; chip.mounted = True
        except (ValueError, OSError) as error:
            messagebox.showerror('PROM 编程失败', str(error), parent=self.root)

    def open_gui(self, root, pause):
        window = tk.Toplevel(root); window.title(self.name)
        s2 = tk.BooleanVar(value=self.s2_prom_boot)
        s3 = tk.BooleanVar(value=self.s3_program)
        def set_s2(): self.s2_prom_boot = s2.get()
        def set_s3(): self.s3_program = s3.get()
        tk.Checkbutton(window, text='S2：从 PROM1 启动', variable=s2, command=set_s2).grid(row=0, column=0, columnspan=3, sticky='w')
        tk.Checkbutton(window, text='S3：PGM 编程电压', variable=s3, command=set_s3).grid(row=1, column=0, columnspan=3, sticky='w')
        status = tk.StringVar()
        tk.Label(window, textvariable=status, anchor='w').grid(row=4, column=0, columnspan=3, sticky='w')
        def load(chip):
            pause()
            path = filedialog.askopenfilename(parent=window, title=f'载入 {chip.name} 镜像', filetypes=[('二进制', '*.bin'), ('全部文件', '*')])
            if path:
                try: chip.mount(path)
                except (OSError, ValueError) as error: messagebox.showerror('载入失败', str(error), parent=window)
        def save(chip):
            pause()
            path = filedialog.asksaveasfilename(parent=window, title=f'导出 {chip.name} 镜像', defaultextension='.bin')
            if path:
                try: chip.export(path)
                except OSError as error: messagebox.showerror('导出失败', str(error), parent=window)
        for row, chip in enumerate(self.chips, 2):
            tk.Label(window, text=f'{chip.name} {chip.start:04X}–{chip.start + chip.size - 1:04X}').grid(row=row, column=0, sticky='w')
            tk.Button(window, text='载入', command=lambda c=chip: load(c)).grid(row=row, column=1)
            tk.Button(window, text='导出', command=lambda c=chip: save(c)).grid(row=row, column=2)
        def refresh():
            if not window.winfo_exists(): return
            status.set('编程等待脉冲' if self.waiting else '编程器空闲')
            window.after(200, refresh)
        refresh()
        return window
