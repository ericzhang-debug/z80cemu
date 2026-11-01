"""Differential speaker driven by two independent digital input pins."""
from collections import deque


class TwoBitSpeaker:
    pins = {'A': 'input', 'B': 'input', 'AUDIO': 'output'}
    levels = (128, 224, 32, 128)

    def __init__(self, cycles, cpu_hz, sample_rate=0):
        if cpu_hz <= 0 or sample_rate < 0: raise ValueError('无效音频时钟')
        self.cycles, self.cpu_hz, self.sample_rate = cycles, cpu_hz, sample_rate
        self.samples = deque(maxlen=max(1, sample_rate * 2))
        self.reset()

    def reset(self):
        self.level = 128
        self.samples.clear()
        self._position = self.cycles() * self.sample_rate // self.cpu_hz

    def _advance(self):
        if not self.sample_rate: return
        position = self.cycles() * self.sample_rate // self.cpu_hz
        count = max(0, position - self._position)
        # A delayed GUI may fall behind; retain at most the bounded queue.
        if count: self.samples.extend(bytes((self.level,)) * min(count, self.samples.maxlen))
        self._position = position

    def set_inputs(self, a, b):
        self._advance()
        self.level = self.levels[(int(bool(b)) << 1) | int(bool(a))]

    def bind_ui(self, root, pause):
        from platform_support.audio_output import WindowsAudioOutput
        self.sample_rate = 22050
        self.samples = deque(maxlen=44100)
        self._position = self.cycles() * self.sample_rate // self.cpu_hz
        self._audio_output = WindowsAudioOutput(self.sample_rate)

    def ui_tick(self):
        self._advance()
        if hasattr(self, '_audio_output') and len(self.samples) >= 2205:
            self._audio_output.submit(bytes(self.samples.popleft() for _ in range(2205)))

    def close_ui(self):
        if hasattr(self, '_audio_output'):
            self._audio_output.close()
            del self._audio_output
