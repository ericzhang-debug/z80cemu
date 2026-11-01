"""TP801 board timing and buses; components are assembled in machines/tp801.py."""
from platform_core import Machine

class TP801Machine(Machine):
    def __init__(self, memory):
        super().__init__({'memory': memory})
        self.ctc = None
        self._ctc_cycles = 0
        self.prom = None
        self._memory_cache = None
        self._tp_batch = False
        self._tp_batch_synced = 0
        self._tp_instruction_start = None

    def rebuild_memory_cache(self):
        """Build a direct CPU lookup after the board's static map is assembled."""
        entries = [None] * 65536
        for device in self.memory:
            for region in device.regions:
                for address in range(region['start'], region['start'] + region['size']):
                    entries[address] = (device.data, region['offset'] + address - region['start'], device.readonly)
        self._memory_cache = entries

    def read(self, address):
        if self._memory_cache is None: return super().read(address)
        entry = self._memory_cache[address]
        return entry[0][entry[1]] if entry is not None else 0xff

    def _sync_ctc(self, offset):
        if self.ctc is not None and offset > self._ctc_cycles:
            self.ctc.tick(offset - self._ctc_cycles)
            self._ctc_cycles = offset

    def acknowledge(self):
        result = super().acknowledge()
        if self._tp_batch: self.cpu.cpu.cycle_limit = 0
        return result

    def reti(self):
        super().reti()
        if self._tp_batch: self.cpu.cpu.cycle_limit = 0

    def io_read(self, address):
        if self._tp_batch: self._begin_batched_io()
        opcode = self.cpu.cpu.data
        offset = 7 if opcode & 255 == 0xdb else 8 + ((opcode >> 15) & 1)
        self._sync_ctc(offset + 3)
        result = super().io_read(address)
        if self._tp_batch: self.cpu.cpu.cycle_limit = 0
        return result

    def io_write(self, address, value):
        if self._tp_batch: self._begin_batched_io()
        opcode = self.cpu.cpu.data
        offset = 7 if opcode & 255 == 0xd3 else 8 + (((opcode >> 15) & 1) << 2)
        self._sync_ctc(offset + 3)
        super().io_write(address, value)
        if self._tp_batch: self.cpu.cpu.cycle_limit = 0

    def _begin_batched_io(self):
        current = self.cpu.cpu.cycles
        self._sync_batched_display(current)
        self._tp_instruction_start = current
        self._ctc_cycles = 0

    def _sync_batched_display(self, cycles):
        elapsed = cycles - self._tp_batch_synced
        if elapsed > 0:
            for device in self._clocked_devices:
                if device is not self.ctc: device.tick(elapsed)
            self._tp_batch_synced = cycles

    def write(self, address, value):
        if self.prom is not None and self.prom.program_enable and self.prom.chips[1].contains(address):
            if self._tp_batch: self._begin_batched_io()
            opcode = self.cpu.cpu.data & 0xffff
            if opcode & 255 == 0xed and opcode >> 8 in (0xa0, 0xa8, 0xb0, 0xb8):
                offset = 11
            else:
                offset = {0x32: 10, 0x77: 4, 0x36: 7}.get(opcode & 255, 0)
            self._sync_ctc(offset)
            if self.prom.intercept_write(address, value):
                if self._tp_batch: self.cpu.cpu.cycle_limit = 0
                return
        if self._memory_cache is None:
            super().write(address, value)
        else:
            entry = self._memory_cache[address]
            if entry is not None and not entry[2]: entry[0][entry[1]] = value & 255

    def run_for(self, cycles):
        if cycles <= 0: return 0
        # Only the board's known display may advance beside an idle CTC.
        if (self.ctc is None or self.prom is None or self.prom.waiting
                or any(ch.running for ch in self.ctc.core.channels)
                or any(device is not self.ctc and device is not getattr(self, 'display', None)
                       for device in self._clocked_devices)):
            return self.step()
        irq = self.interrupt_candidate() is not None
        if not irq:
            for device in self._irq_sources:
                if device.irq_active(): irq = True; break
        self.cpu.set_interrupt(irq)
        self._tp_batch = True
        self._tp_batch_synced = 0
        self._tp_instruction_start = None
        self._ctc_cycles = 0
        try:
            elapsed = self.cpu.run(cycles)
            self._sync_batched_display(elapsed)
            if self._tp_instruction_start is not None:
                self._sync_ctc(elapsed - self._tp_instruction_start)
        finally:
            self._tp_batch = False
        self.cycles += elapsed
        return elapsed

    def step(self):
        # CTC2 runs while the processor is held waiting for a PROM pulse.
        if self.prom is not None and self.prom.waiting:
            elapsed = 4
            self.ctc.tick(elapsed)
            self.cycles += elapsed
            for device in self._clocked_devices:
                if device is not self.ctc: device.tick(elapsed)
            return elapsed
        self._ctc_cycles = 0
        irq = self.interrupt_candidate() is not None
        if not irq:
            for device in self._irq_sources:
                if device.irq_active(): irq = True; break
        self.cpu.set_interrupt(irq)
        elapsed = self.cpu.step()
        self._sync_ctc(elapsed)
        self.cycles += elapsed
        for device in self._clocked_devices:
            if device is not self.ctc: device.tick(elapsed)
        return elapsed
