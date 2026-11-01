"""Z80 CTC component."""
class CTCChannel:
    def __init__(self):
        self.control = 3
        self.constant = 256
        self.count = 256
        self.phase = 0
        self.wait_constant = False
        self.running = False
        self.wait_trigger = False
        self.pending = False
        self.in_service = False
        self.trigger_level = False
        self.output_pulses = 0

class CTC:
    def __init__(self, pulse):
        self.channels = [CTCChannel() for _ in range(4)]
        self.vector = 0
        self.pulse = pulse
        self.links = {}
    def write(self, i, value):
        ch = self.channels[i]
        if ch.wait_constant:
            ch.constant = value or 256
            # The timer begins after the control write, including its startup delay.
            # This timing matters to TPBUG's one-instruction CTC2/NMI sequence.
            ch.count, ch.phase = ch.constant, -4 if not ch.control & 0x40 else 0
            ch.wait_constant = False
            ch.wait_trigger = bool(ch.control & 0x08) and not bool(ch.control & 0x40)
            ch.running = not ch.wait_trigger
        elif not value & 1:
            if i == 0: self.vector = value & 0xf8
        else:
            ch.control = value
            ch.wait_constant = bool(value & 4)
            if value & 2:
                ch.running = False
                ch.pending = False
                ch.phase = 0
            if not value & 0x80: ch.pending = False
    def read(self, i):
        return self.channels[i].count & 255
    def trigger(self, i, edges=1):
        ch = self.channels[i]
        if ch.wait_trigger:
            ch.wait_trigger = False
            ch.running = True
            return
        if ch.running and ch.control & 0x40:
            self._advance(i, edges)
    def set_trigger(self, i, level):
        ch = self.channels[i]
        level = bool(level)
        old = ch.trigger_level
        ch.trigger_level = level
        if old != level and level == bool(ch.control & 0x10):
            self.trigger(i)
    def connect(self, source, target):
        if source not in range(3) or target not in range(4):
            raise ValueError('CTC 输出为 0–2，输入为 0–3')
        links = {channel:set(targets) for channel,targets in self.links.items()}
        links.setdefault(source,set()).add(target)
        def reaches_source(node,seen):
            if node == source: return True
            if node in seen: return False
            seen.add(node)
            return any(reaches_source(next_node,seen) for next_node in links.get(node,()))
        if reaches_source(target,set()): raise ValueError('CTC 连线不能形成环路')
        self.links = links
    def _advance(self, i, ticks):
        ch = self.channels[i]
        if not ticks: return
        if ticks < ch.count:
            ch.count -= ticks
            return
        ticks -= ch.count
        occurrences = 1 + ticks // ch.constant
        ch.count = ch.constant - ticks % ch.constant
        if ch.control & 0x80: ch.pending = True
        if i < 3:
            ch.output_pulses += occurrences
            self.pulse(i, occurrences)
            for target in sorted(self.links.get(i,())): self.trigger(target, occurrences)
    def tick(self, cycles, skip=()):
        # Advance all running timers to the next terminal-count edge together.
        # This preserves the order of edges when channels are chained, regardless
        # of channel number or how the caller partitions its cycle budget.
        remaining = cycles
        while remaining > 0:
            active = [(i, ch, 256 if ch.control & 0x20 else 16)
                      for i, ch in enumerate(self.channels)
                      if i not in skip and ch.running and not ch.control & 0x40]
            if not active: return
            step = min(remaining, min(ch.count * divisor - ch.phase for _,ch,divisor in active))
            due = []
            for i, ch, divisor in active:
                ch.phase += step
                if ch.phase >= 0:
                    ticks, ch.phase = divmod(ch.phase, divisor)
                    if ticks: due.append((i, ticks))
            for i, ticks in due:self._advance(i, ticks)
            remaining -= step
    def candidate(self):
        for i, ch in enumerate(self.channels):
            if ch.in_service: return None
            if ch.pending: return i
        return None
    def acknowledge(self, i):
        ch = self.channels[i]; ch.pending = False; ch.in_service = True
        return self.vector | (i << 1)
    def reti(self):
        for ch in self.channels:
            if ch.in_service:
                ch.in_service = False; return True
        return False

class Z80CTC:
    def open_gui(self, root, pause):
        from ui.component_views import device_window
        return device_window(root, self, pause)
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{f'CLK/TRG{i}': 'input' for i in range(4)},
            **{f'ZC/TO{i}': 'output' for i in range(3)},
            **{n: 'input' for n in ('CLK', '/CE', '/IORQ', '/RD', '/M1', '/RESET', 'IEI', 'CS0', 'CS1')},
            'IEO': 'output', '/INT': 'output'}

    def __init__(self, base, pulse=None):
        self.base = base
        self.pulse = pulse or (lambda channel, count: None)
        self.reset()

    def reset(self): self.core = CTC(self.pulse)
    def read_port(self, address): return self.core.read((address - self.base) & 3)
    def write_port(self, address, value): self.core.write((address - self.base) & 3, value)
    def tick(self, cycles): self.core.tick(cycles)
    def candidate(self): return self.core.candidate()
    def acknowledge(self, candidate): return self.core.acknowledge(candidate)
    def reti(self): return self.core.reti()
    def in_service(self):
        a, b, c, d = self.core.channels
        return a.in_service or b.in_service or c.in_service or d.in_service

