"""PCM cassette transport with cycle-timed input and output signal levels."""
from pathlib import Path
import wave


class VTechCassette:
    pins = {'EAR': 'output', 'MIC': 'input'}
    def __init__(self, cycles, cpu_hz):
        self.cycles, self.cpu_hz = cycles, cpu_hz
        self.root = None
        self.pause = lambda: None
        self.pending = None
        self.samples = b''
        self.rate = 0
        self.play_start = 0
        self.output_path = None
        self.edges = []
        self.last_level = None
        self.status = '空闲'
        self._asked_load = self._asked_save = False
        self._window = None
        self._progress_mode = None
        self._play_total = 0
        self._record_start = None

    def reset(self):
        if self.output_path is not None and self.edges:
            self.finish_recording()
        self.pending = None
        self.samples = b''
        self.output_path = None
        self.edges = []
        self._asked_load = self._asked_save = False
        self._progress_mode = None
        self._play_total = 0

    def bind_ui(self, root, pause): self.root, self.pause = root, pause

    def close_ui(self):
        if self.output_path is not None and self.edges:
            self.finish_recording()

    def request_load(self):
        if not self.samples and not self._asked_load:
            self._asked_load = True
            self.pending = 'load'

    def request_save(self):
        if self.output_path is None and not self._asked_save:
            self._asked_save = True
            self.pending = 'save'

    def finish_command(self):
        """Rearm automatic dialogs when the host returns to its command prompt."""
        if self.pending: return
        if not self.samples: self._asked_load = False
        if self.output_path is None: self._asked_save = False

    def ui_tick(self):
        if self.pending and self.root is not None:
            operation, self.pending = self.pending, None
            self.pause()
            self.root.after_idle(self._choose_load if operation == 'load' else self._choose_save)
        if self.output_path is not None and self.edges and self.cycles() - self.edges[-1][0] > self.cpu_hz:
            self.finish_recording()

    def load_wav(self, path):
        with wave.open(str(path), 'rb') as src:
            width, channels, rate = src.getsampwidth(), src.getnchannels(), src.getframerate()
            if src.getcomptype() != 'NONE' or width not in (1, 2) or channels not in (1, 2):
                raise ValueError('仅支持 8/16 位单声道或立体声 PCM WAV')
            raw = src.readframes(src.getnframes())
        step = width * channels
        values = bytearray()
        for pos in range(0, len(raw) - step + 1, step):
            samples = [raw[pos + ch] - 128 if width == 1 else
                       int.from_bytes(raw[pos + ch * width:pos + ch * width + width], 'little', signed=True) // 256
                       for ch in range(channels)]
            values.append(1 if sum(samples) / channels > 5 else 0)
        self.samples, self.rate = bytes(values), rate
        self.play_start = self.cycles()
        self._play_total = len(self.samples)
        self._progress_mode = 'play'
        self._asked_load = True
        self.status = f'正在播放：{Path(path).name}'

    def input_level(self):
        if not self.samples: return False
        index = (self.cycles() - self.play_start) * self.rate // self.cpu_hz
        if index >= len(self.samples):
            self.samples = b''
            self.status = '磁带播放结束'
            return False
        return bool(self.samples[max(0, index)])

    def start_recording(self, path):
        self.output_path = Path(path)
        self.edges = []
        self.last_level = None
        self._record_start = None
        self._progress_mode = 'record'
        self.status = f'正在录制：{self.output_path.name}'
        self._asked_save = True

    def output_level(self, level):
        level = bool(level)
        if self.output_path is not None and level != self.last_level:
            cycle = self.cycles()
            if self._record_start is None: self._record_start = cycle
            self.edges.append((cycle, level))
            self.last_level = level

    def finish_recording(self):
        if self.output_path is None: return
        rate = 44100
        samples = bytearray()
        if self.edges:
            start = self.edges[0][0]
            for index, (cycle, level) in enumerate(self.edges):
                end = self.edges[index + 1][0] if index + 1 < len(self.edges) else cycle + self.cpu_hz // 20
                count = max(0, (end - start) * rate // self.cpu_hz - len(samples))
                samples.extend(bytes([224 if level else 32]) * count)
        with wave.open(str(self.output_path), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(1); out.setframerate(rate); out.writeframes(samples)
        self.status = f'录制完成：{self.output_path.name}'
        self.output_path = None
        self.edges = []
        self._progress_mode = None

    def progress(self):
        """Return mode, elapsed seconds and total seconds (None for recording)."""
        if self._progress_mode == 'play' and self.rate and self._play_total:
            position = min(self._play_total, max(0, (self.cycles() - self.play_start) * self.rate // self.cpu_hz))
            return 'play', position / self.rate, self._play_total / self.rate
        if self._progress_mode == 'record' and self.output_path is not None:
            elapsed = 0 if self._record_start is None else max(0, self.cycles() - self._record_start)
            return 'record', elapsed / self.cpu_hz, None
        return None, 0.0, None

    def _selected(self, path):
        from tkinter import messagebox
        window = self.open_gui(self.root, self.pause)
        messagebox.showinfo('磁带已选择', f'已选择：{path}\n请点击主窗口“开始”继续。', parent=window)

    def _choose_load(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title='读取 Laser 310 磁带', filetypes=[('PCM WAV', '*.wav')])
        if not path: return
        try: self.load_wav(path)
        except (OSError, ValueError, wave.Error) as error: messagebox.showerror('读取失败', str(error), parent=self.root)
        else: self._selected(path)

    def _choose_save(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(parent=self.root, title='录制 Laser 310 磁带', defaultextension='.wav', filetypes=[('PCM WAV', '*.wav')])
        if path:
            self.start_recording(path)
            self._selected(path)

    def open_gui(self, root, pause):
        import tkinter as tk
        from tkinter import ttk
        self.bind_ui(root, pause)
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return self._window
        window = tk.Toplevel(root); window.title(self.name)
        self._window = window
        status = ttk.Label(window); status.pack(padx=4, pady=2)
        progress = ttk.Progressbar(window, mode='determinate', maximum=100, length=220)
        progress.pack(fill='x', padx=6, pady=2)
        detail = ttk.Label(window, text='等待选择磁带'); detail.pack(padx=4, pady=2)
        bar = ttk.Frame(window); bar.pack(padx=4, pady=2)
        tk.Button(bar, text='读取 WAV…', command=lambda: (pause(), self._choose_load())).pack(side='left')
        tk.Button(bar, text='录制 WAV…', command=lambda: (pause(), self._choose_save())).pack(side='left')
        tk.Button(bar, text='停止录制', command=self.finish_recording).pack(side='left')
        scheduled = [None]
        def update():
            scheduled[0] = None
            if not window.winfo_exists(): return
            status.config(text=self.status)
            mode, elapsed, total = self.progress()
            if mode == 'play':
                progress.configure(mode='determinate', value=elapsed * 100 / total)
                detail.config(text=f'读取：{elapsed:.1f} / {total:.1f} 秒（{elapsed * 100 / total:.0f}%）')
            elif mode == 'record':
                progress.configure(mode='indeterminate')
                progress.step(5)
                detail.config(text=f'录制：{elapsed:.1f} 秒')
            else:
                progress.configure(mode='determinate', value=0)
                detail.config(text='等待选择磁带')
            scheduled[0] = window.after(200, update)
        def on_destroy(event):
            if event.widget is not window: return
            if scheduled[0] is not None:
                window.after_cancel(scheduled[0])
                scheduled[0] = None
            if self._window is window: self._window = None
        window.bind('<Destroy>', on_destroy, add='+')
        update()
        return window
