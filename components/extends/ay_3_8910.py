"""AY-3-8910 register interface, tone/noise/envelope and optional PCM output.

Clocked in CPU cycles.  Analog resistor loading and bus wait states are not
modelled; port pin callbacks let a machine wire its own joystick and cassette.
"""
from collections import deque

class AY38910:
    batch_tick_safe = True
    batch_io_safe = True
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{f'IOA{i}': 'bidirectional' for i in range(8)},
            **{f'IOB{i}': 'bidirectional' for i in range(8)},
            'BDIR': 'input', 'BC1': 'input', 'CLOCK': 'input', 'AUDIO': 'output'}
    _amplitude = (0, 1, 2, 3, 4, 6, 9, 13, 18, 25, 35, 49, 69, 97, 137, 193)
    _masks = (255,15,255,15,255,15,31,255,31,31,31,255,255,15,255,255)

    def __init__(self, base=0xa0, cpu_hz=3_579_545, clock_hz=1_789_772, read_a=None, read_b=None, write_a=None, write_b=None):
        self.base, self.cpu_hz, self.clock_hz = base, cpu_hz, clock_hz
        self.read_pins = (read_a or (lambda: 0xff), read_b or (lambda: 0xff))
        self.write_pins = (write_a or (lambda value: None), write_b or (lambda value: None))
        self.sample_rate = 0
        self.samples = deque(maxlen=44100)
        self.reset()

    def reset(self):
        self.registers = bytearray(16)
        self.selected = 0
        self.clock_phase = self.sample_phase = 0
        self.tone_counter = [0, 0, 0]
        self.tone_state = [0, 0, 0]
        self.noise_counter = 0
        self.noise_lfsr = 0x1ffff
        self.envelope_counter = 0
        self.envelope_step = 0
        self.envelope_cycle = 0
        self.envelope_holding = False
        self.samples.clear()

    def read_port(self, address):
        if (address - self.base) & 3 != 2: return 0xff
        if self.selected in (14, 15):
            index = self.selected - 14
            if not self.registers[7] & (0x40 << index): return self.read_pins[index]() & 0xff
        return self.registers[self.selected]

    def write_port(self, address, value):
        port = (address - self.base) & 3
        if port == 0: self.selected = value & 15
        elif port == 1:
            reg = self.selected
            previous = self.registers[reg]
            self.registers[reg] = value & self._masks[reg]
            if reg == 13:
                self.envelope_counter = self.envelope_step = self.envelope_cycle = 0
                self.envelope_holding = False
            elif reg == 7:
                for index in (0, 1):
                    mask = 0x40 << index
                    if not previous & mask and self.registers[7] & mask:
                        self.write_pins[index](self.registers[14 + index])
            elif reg in (14, 15) and self.registers[7] & (0x40 << (reg - 14)):
                self.write_pins[reg - 14](self.registers[reg])

    def _advance(self, clocks):
        r = self.registers
        for channel in range(3):
            period = max(1, r[channel * 2] | ((r[channel * 2 + 1] & 15) << 8)) * 8
            changes, self.tone_counter[channel] = divmod(self.tone_counter[channel] + clocks, period)
            self.tone_state[channel] ^= changes & 1
        noise_period = max(1, r[6] & 31) * 16
        changes, self.noise_counter = divmod(self.noise_counter + clocks, noise_period)
        for _ in range(changes):
            self.noise_lfsr = (self.noise_lfsr >> 1) | (((self.noise_lfsr ^ (self.noise_lfsr >> 3)) & 1) << 16)
        env_period = max(1, r[11] | (r[12] << 8)) * 256
        changes, self.envelope_counter = divmod(self.envelope_counter + clocks, env_period)
        if not self.envelope_holding and changes:
            total = self.envelope_step + changes
            cycles, self.envelope_step = divmod(total, 16)
            if cycles:
                self.envelope_cycle += cycles
                if not r[13] & 8 or r[13] & 1:
                    self.envelope_holding = True
                    self.envelope_step = 15
                    self.envelope_cycle = 1

    def _sample(self):
        r, shape = self.registers, self.registers[13]
        attack = bool(shape & 4)
        if shape & 2 and self.envelope_cycle & 1: attack = not attack
        if self.envelope_holding and not shape & 8: env = 0
        else: env = self.envelope_step if attack else 15 - self.envelope_step
        total = 0
        for channel in range(3):
            tone = bool(r[7] & (1 << channel)) or self.tone_state[channel]
            noise = bool(r[7] & (8 << channel)) or bool(self.noise_lfsr & 1)
            level = env if r[8 + channel] & 16 else r[8 + channel] & 15
            total += self._amplitude[level] * (1 if tone and noise else -1)
        return 128 + total * 110 // (3 * 193)

    def tick(self, cycles):
        if not self.sample_rate:
            clocks, self.clock_phase = divmod(self.clock_phase + cycles * self.clock_hz, self.cpu_hz)
            self._advance(clocks)
            return
        while cycles:
            take = min(cycles, max(1, (self.cpu_hz - self.sample_phase + self.sample_rate - 1) // self.sample_rate))
            clocks, self.clock_phase = divmod(self.clock_phase + take * self.clock_hz, self.cpu_hz)
            self._advance(clocks)
            self.sample_phase += take * self.sample_rate
            cycles -= take
            if self.sample_phase >= self.cpu_hz:
                self.sample_phase -= self.cpu_hz
                self.samples.append(self._sample())

    def bind_ui(self, root, pause):
        from platform_support.audio_output import WindowsAudioOutput
        self.sample_rate = 22050
        self._audio_output = WindowsAudioOutput(self.sample_rate)

    def ui_tick(self):
        if hasattr(self, '_audio_output') and len(self.samples) >= 2205:
            self._audio_output.submit(bytes(self.samples.popleft() for _ in range(2205)))

    def close_ui(self):
        if hasattr(self, '_audio_output'):
            self._audio_output.close()
            del self._audio_output
