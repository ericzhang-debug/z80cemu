"""Cycle-clocked MSX cassette signal interface backed by PCM WAV files.

Motor and output are digital lines; the input is the thresholded PCM signal.
The firmware generates and decodes its own FSK waveform through those lines.
"""
import io
import wave
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class MSXCassette:
    batch_tick_safe = True
    batch_io_safe = True
    pins = {'MOTOR': 'input', 'CASW': 'input', 'CASRD': 'output'}
    name = 'MSX 磁带机'

    def __init__(self, cpu_hz=3_579_545, sample_rate=44100):
        self.cpu_hz, self.sample_rate = cpu_hz, sample_rate
        self.media = None
        self.path = None
        self._segments = []
        self._ui_root = self._pause = None
        self._window = None
        self._recorded_cycles = 0
        self.reset()

    def reset(self):
        unsaved = bool(getattr(self, 'motor', False) and self.media == 'record' and self._segments)
        self.motor = False
        self.output = 1
        self.position = self.play_phase = self.motor_cycles = 0
        self.prompted = False
        self.pending_save = unsaved or getattr(self, 'pending_save', False)

    def set_pins(self, motor, output):
        motor, output = bool(motor), int(bool(output))
        if self.motor and not motor:
            if self.media == 'record' and self._segments: self.pending_save = True
            self.prompted = False
            self.motor_cycles = 0
        elif motor and not self.motor:
            self.motor_cycles = 0
        self.motor, self.output = motor, output

    def read_level(self):
        if self.motor and self.media == 'play' and self.position < len(self.waveform):
            return self.waveform[self.position]
        return 1

    def tick(self, cycles):
        if not self.motor: return
        self.motor_cycles += cycles
        if self.media == 'play':
            advance, self.play_phase = divmod(self.play_phase + cycles * self.input_rate, self.cpu_hz)
            self.position = min(len(self.waveform), self.position + advance)
        elif self.media == 'record':
            self._recorded_cycles += cycles
            if self._segments and self._segments[-1][0] == self.output:
                old, duration = self._segments[-1]
                self._segments[-1] = (old, duration + cycles)
            else: self._segments.append((self.output, cycles))

    def load_wav(self, path):
        with wave.open(str(path), 'rb') as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            if channels not in (1, 2) or width not in (1, 2, 3, 4) or not rate:
                raise ValueError('仅支持单声道或双声道的 8/16/24/32 位 PCM WAV')
            raw = source.readframes(source.getnframes())
        frame_size = channels * width
        waveform = bytearray(len(raw) // frame_size)
        for n in range(len(waveform)):
            level = 0
            for channel in range(channels):
                off = n * frame_size + channel * width
                sample = int.from_bytes(raw[off:off + width], 'little', signed=width != 1)
                level += sample - 128 if width == 1 else sample
            waveform[n] = int(level >= 0)
        self.waveform, self.input_rate = waveform, rate
        self.position = self.play_phase = 0
        self.path, self.media = str(path), 'play'
        self.pending_save = False

    def start_recording(self, path=None):
        self.path, self.media = str(path) if path else None, 'record'
        self._segments = []
        self._recorded_cycles = 0
        self.pending_save = False

    def wav_bytes(self):
        samples = bytearray()
        total_cycles = written = 0
        for level, cycles in self._segments:
            total_cycles += cycles
            count = total_cycles * self.sample_rate // self.cpu_hz - written
            samples.extend(bytes((0xe0 if level else 0x20,)) * count)
            written += count
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as target:
            target.setnchannels(1); target.setsampwidth(1); target.setframerate(self.sample_rate)
            target.writeframes(samples)
        return buffer.getvalue()

    def save_wav(self, path=None):
        target = path or self.path
        if not target: raise ValueError('未选择录制文件')
        Path(target).write_bytes(self.wav_bytes())
        self.pending_save = False

    def bind_ui(self, root, pause): self._ui_root, self._pause = root, pause
    def close_ui(self):
        if self.media == 'record' and self._segments and self.path: self.save_wav()
        if self._window is not None and self._window.winfo_exists():
            self._window._stop_tape_progress()
            self._window.destroy()
        self._window = None
        self._ui_root = None

    def _choose_media(self, parent):
        self._pause()
        choice = messagebox.askyesnocancel('MSX 磁带', '选择“是”读取 WAV，选择“否”录制 WAV。', parent=parent)
        if choice is None: return
        try:
            if choice:
                path = filedialog.askopenfilename(parent=parent, title='读取磁带', filetypes=[('WAV', '*.wav')])
                if path: self.load_wav(path)
            else:
                path = filedialog.asksaveasfilename(parent=parent, title='录制磁带', defaultextension='.wav', filetypes=[('WAV', '*.wav')])
                if path: self.start_recording(path)
        except (OSError, ValueError, wave.Error) as error:
            messagebox.showerror('磁带错误', str(error), parent=parent)
            return
        if path:
            window = self.open_gui(self._ui_root, self._pause)
            action = '读取' if choice else '录制'
            messagebox.showinfo('磁带已选择', f'已选择{action}文件：\n{path}\n\n请点击主窗口的“开始”继续。', parent=window)

    def ui_tick(self):
        if self._ui_root is None: return
        if self.pending_save:
            try: self.save_wav()
            except OSError as error:
                self.pending_save = False
                self._pause()
                messagebox.showerror('磁带保存失败', str(error), parent=self._ui_root)
        if self.motor and not self.media and not self.prompted and self.motor_cycles >= self.cpu_hz // 10:
            self.prompted = True
            self._choose_media(self._ui_root)

    def open_gui(self, root, pause):
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return self._window
        self.bind_ui(root, pause)
        window = tk.Toplevel(root); window.title(self.name)
        self._window = window
        label = ttk.Label(window); label.pack(padx=4, pady=4)
        progress = ttk.Progressbar(window, orient='horizontal', length=220, mode='determinate', maximum=100)
        progress.pack(fill='x', padx=6, pady=(0, 2))
        progress_label = ttk.Label(window); progress_label.pack(padx=4, pady=(0, 3))
        def choose(): self._choose_media(window)
        def eject():
            pause()
            if self.media == 'record' and self._segments and self.path: self.save_wav()
            self.media, self.path = None, None
        bar = ttk.Frame(window); bar.pack(padx=4, pady=3)
        tk.Button(bar, text='选择磁带…', command=choose).pack(side='left')
        tk.Button(bar, text='取出', command=eject).pack(side='left', padx=3)
        state = {'animating': False, 'last_cycles': self._recorded_cycles, 'timer': None}
        def stop_progress():
            if state['timer'] is not None:
                window.after_cancel(state['timer'])
                state['timer'] = None
            if state['animating']:
                if progress.winfo_exists(): progress.stop()
                state['animating'] = False
        window._stop_tape_progress = stop_progress
        def close_window():
            stop_progress()
            window.destroy()
        window.protocol('WM_DELETE_WINDOW', close_window)
        progress.bind('<Destroy>', lambda event: progress.stop() if event.widget is progress else None, add='+')
        window.bind('<Destroy>', lambda event: stop_progress() if event.widget is window else None, add='+')
        def update():
            state['timer'] = None
            if not window.winfo_exists(): return
            filename = Path(self.path).name if self.path else '未装入磁带'
            label.config(text=f'{"电机运行" if self.motor else "电机停止"}  {filename}')
            if self.media == 'play':
                if state['animating']: progress.stop(); state['animating'] = False
                length = len(self.waveform)
                percent = self.position * 100 / length if length else 100.0
                progress.configure(mode='determinate', value=percent)
                progress_label.config(text=f'读取进度：{percent:.1f}%  ({self.position / self.input_rate:.1f} / {length / self.input_rate:.1f} 秒)')
            elif self.media == 'record':
                progress.configure(mode='indeterminate')
                advancing = self.motor and self._recorded_cycles != state['last_cycles']
                if advancing and not state['animating']:
                    progress.start(80); state['animating'] = True
                elif not advancing and state['animating']:
                    progress.stop(); state['animating'] = False
                state['last_cycles'] = self._recorded_cycles
                seconds = int(self._recorded_cycles / self.cpu_hz)
                progress_label.config(text=f'录制时长：{seconds // 60:02d}:{seconds % 60:02d}（录制总长度未预设）')
            else:
                if state['animating']: progress.stop(); state['animating'] = False
                progress.configure(mode='determinate', value=0)
                progress_label.config(text='未装入磁带')
            state['timer'] = window.after(200, update)
        update()
        return window
