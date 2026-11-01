"""Laser 310 memory decoding and board-level signal connections."""
from platform_core import Machine


class Laser310Machine(Machine):
    def __init__(self, memory, clock_hz):
        super().__init__({'memory': memory})
        self.clock_hz = clock_hz
        self.screen = self.keyboard = self.cassette = self.speaker = None
        self._running_batch = False
        # The board's memory map is static after assembly. Resolve it once so
        # every CPU fetch does not search each memory device and its regions.
        self._memory_lookup = [None] * 65536
        for device in self.memory:
            for region in device.regions:
                start, size = region['start'], region['size']
                entry = (device.data, region['offset'] - start, device.readonly)
                self._memory_lookup[start:start + size] = [entry] * size

    def now_cycles(self):
        return self.cycles + (self.cpu.cpu.cycles if self._running_batch else 0)

    def read(self, address):
        if 0x6800 <= address <= 0x6fff:
            pc = self.cpu.cpu.pc
            if 0x2efd <= pc <= 0x2f05 and self.cassette:
                # Returning to the ordinary BASIC keyboard scan ends the
                # previous cassette command, including a cancelled dialog.
                self.cassette.finish_command()
            # BASIC's tape pulse-input loop; keyboard scanning accesses the
            # same hardware address but executes in a different ROM region.
            if self.cassette and (0x35e7 <= pc <= 0x35f2 or 0x3790 <= pc <= 0x37f0):
                self.cassette.request_load()
                if self.cassette.pending and self._running_batch: self.cpu.cpu.cycle_limit = 0
            keys = self.keyboard.read(address) if self.keyboard else 0x3f
            tape = 0 if self.cassette and self.cassette.input_level() else 0x40
            frame = self.now_cycles() % (self.clock_hz // 50)
            return keys | tape | (0x80 if frame < self.clock_hz // 50 - self.clock_hz // 400 else 0)
        entry = self._memory_lookup[address]
        return entry[0][address + entry[1]] if entry is not None else 0xff

    def write(self, address, value):
        if 0x6800 <= address <= 0x6fff:
            if self.screen: self.screen.set_mode(value)
            if self.speaker: self.speaker.set_inputs(value & 1, value & 0x20)
            if self.cassette:
                if 0x352a <= self.cpu.cpu.pc < 0x3555:
                    self.cassette.request_save()
                    if self.cassette.pending and self._running_batch: self.cpu.cpu.cycle_limit = 0
                self.cassette.output_level(value & 4)
            return
        entry = self._memory_lookup[address]
        if entry is not None and not entry[2]:
            data, offset, _ = entry
            index = address + offset
            if 0x7000 <= address <= 0x77ff and self.screen and data[index] != value:
                self.screen.changed()
            data[index] = value & 0xff

    def run_for(self, cycles):
        # Frame-sync also drives the Z80 interrupt line. End batches at the
        # next edge so interrupt and keyboard timing keep advancing.
        if cycles <= 0: return 0
        period, blank = self.clock_hz // 50, self.clock_hz // 400
        phase = self.cycles % period
        active = phase >= period - blank
        remaining = period - phase if active else period - blank - phase
        self.cpu.set_interrupt(active)
        self._running_batch = True
        try: elapsed = self.cpu.run(min(cycles, max(1, remaining)))
        finally: self._running_batch = False
        self.cycles += elapsed
        return elapsed
