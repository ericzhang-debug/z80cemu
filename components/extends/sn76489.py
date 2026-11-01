"""SN76489AN-style programmable sound generator.

The oscillator is clocked in CPU-cycle increments; the optional bounded PCM
queue contains unsigned 8-bit mono samples and can be consumed by an audio
frontend. This does not model READY/bus wait states or analog output filtering.
"""
from collections import deque

class SN76489:
    batch_tick_safe = True
    batch_io_safe = True
    name = 'SN76489AN 声音发生器'
    pins = {**{f'D{i}': 'input' for i in range(8)},
            '/CE': 'input', '/WE': 'input', 'CLK': 'input',
            'READY': 'output', 'AUDIO': 'output'}

    def bind_ui(self, root, pause):
        from platform_support.audio_output import WindowsAudioOutput
        self.sample_rate = 22050
        self.samples = deque(maxlen=44100)
        self._audio_output = WindowsAudioOutput(22050)

    def ui_tick(self):
        if hasattr(self, '_audio_output') and len(self.samples) >= 2205:
            self._audio_output.submit(bytes(self.samples.popleft() for _ in range(2205)))

    def close_ui(self):
        if hasattr(self, '_audio_output'):
            self._audio_output.close()
            del self._audio_output

    def __init__(self, cpu_hz=4_000_000, clock_hz=3_579_545, sample_rate=0):
        if cpu_hz <= 0 or clock_hz <= 0 or sample_rate < 0:
            raise ValueError('clock and sample rates must be positive')
        self.cpu_hz, self.clock_hz, self.sample_rate = cpu_hz, clock_hz, sample_rate
        self.samples = deque(maxlen=max(1, sample_rate * 2))
        self.reset()

    def reset(self):
        self.tone = [0, 0, 0]
        self.volume = [15, 15, 15, 15]
        self.noise = 0
        self.latch = 0
        self.tone_count = [1, 1, 1]
        self.level = [0, 0, 0]
        self.noise_count = 32
        self.lfsr = 0x4000
        self.cpu_phase = 0
        self.divider_phase = 0
        self.sample_phase = 0
        self.samples.clear()

    def read_port(self, address): return 0xff

    def write_port(self, address, value):
        value &= 255
        if value & 0x80:
            self.latch = (value >> 4) & 7
            data = value & 15
            if self.latch & 1:
                self.volume[self.latch >> 1] = data
            elif self.latch == 6:
                self.noise = data & 7
                self.lfsr = 0x4000
            else:
                channel = self.latch >> 1
                self.tone[channel] = (self.tone[channel] & 0x3f0) | data
        elif self.latch & 1:
            self.volume[self.latch >> 1] = value & 15
        elif self.latch == 6:
            self.noise = value & 7
            self.lfsr = 0x4000
        else:
            channel = self.latch >> 1
            self.tone[channel] = (self.tone[channel] & 15) | ((value & 0x3f) << 4)

    def _noise_shift(self):
        feedback = (self.lfsr & 1) ^ ((self.lfsr >> 1) & 1) if self.noise & 4 else self.lfsr & 1
        self.lfsr = (self.lfsr >> 1) | (feedback << 14)

    def _advance_divided(self, ticks):
        # Advance to the next counter transition, preserving ordering for tone 2
        # driving the noise generator. Each tick represents 16 input clocks.
        while ticks:
            fixed_noise = (self.noise & 3) != 3
            span = min(ticks, *self.tone_count,
                       self.noise_count if fixed_noise else ticks)
            ticks -= span
            for i in range(3): self.tone_count[i] -= span
            if fixed_noise: self.noise_count -= span
            for i in range(3):
                if not self.tone_count[i]:
                    self.tone_count[i] = self.tone[i] or 0x400
                    self.level[i] ^= 1
                    if i == 2 and not fixed_noise and self.level[i] == 1:
                        self._noise_shift()
            if fixed_noise and not self.noise_count:
                self.noise_count = (32, 64, 128)[self.noise & 3]
                self._noise_shift()

    def advance_clocks(self, clocks):
        if clocks < 0: raise ValueError('negative clocks')
        ticks, self.divider_phase = divmod(self.divider_phase + clocks, 16)
        self._advance_divided(ticks)

    def sample(self):
        # Approximately 2 dB attenuation per step; 15 is silence.
        levels = (1.0, .7943, .6310, .5012, .3981, .3162, .2512, .1995,
                  .1585, .1259, .1, .0794, .0631, .0501, .0398, 0.0)
        output = sum(levels[self.volume[i]] * (1 if self.level[i] else -1) for i in range(3))
        output += levels[self.volume[3]] * (1 if self.lfsr & 1 else -1)
        return max(0, min(255, round(128 + output * 31)))

    def tick(self, cycles):
        if cycles < 0: raise ValueError('negative cycles')
        clocks, self.cpu_phase = divmod(self.cpu_phase + cycles * self.clock_hz, self.cpu_hz)
        if not self.sample_rate:
            self.advance_clocks(clocks)
            return
        while clocks:
            remaining = (self.clock_hz - self.sample_phase + self.sample_rate - 1) // self.sample_rate
            span = min(clocks, remaining)
            self.advance_clocks(span)
            clocks -= span
            self.sample_phase += span * self.sample_rate
            while self.sample_phase >= self.clock_hz:
                self.sample_phase -= self.clock_hz
                self.samples.append(self.sample())
