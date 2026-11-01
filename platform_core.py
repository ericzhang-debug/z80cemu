"""Machine assembly and bus contracts, independent of Tk."""
from components.ram import RAM
from components.rom import ROM
from components.cpu import Z80

class Machine:
    def __init__(self, config, cpu_factory=Z80):
        self.memory = []
        for spec in config['memory']:
            if spec['type'] not in ('rom', 'ram'):
                raise ValueError(f"未知存储器类型: {spec['type']}")
            component = ROM if spec['type'] == 'rom' else RAM
            name = spec['name']; index = 2
            used = {device.name for device in self.memory}
            while name in used:
                name = f"{spec['name']} ({index})"; index += 1
            device = component(name, spec['start'], spec['size'], spec.get('regions'))
            if any(a['start'] < b['start'] + b['size'] and b['start'] < a['start'] + a['size'] for other in self.memory for a in device.regions for b in other.regions):
                raise ValueError(f"内存地址重叠: {device.name}")
            self.memory.append(device)
        self.ports = {}
        self.io_decoders = []
        self.io_history = {}
        self.io_counts = {}
        self.io_low_history = {}
        self.io_low_counts = {}
        self.cycles = 0
        self.cpu = cpu_factory(self)
        self.components = [self.cpu, *self.memory]
        # None opens all components with a GUI; a sequence selects names.
        self.auto_open_windows = None
        self.input_bindings = []
        self._clocked_devices = []
        self._daisy_devices = []
        self._reti_devices = []
        self._irq_sources = []
        self._reset_devices = []
        self.allow_batched_execution = False
        self._batch_active = False
        self._batch_synced = 0
        self._batch_irq_level = False
        self._batch_unsafe_io = False

    def bind_keyboard(self, keyboard, target):
        """Route host key events from a component's window to a keyboard device."""
        if not all(any(device is component for component in self.components) for device in (keyboard, target)):
            raise ValueError('键盘和目标组件必须先挂载')
        if keyboard is target or not callable(getattr(keyboard, 'key_event', None)):
            raise ValueError('键盘组件必须提供 key_event，目标必须是另一组件')
        if any(a is keyboard and b is target for a, b in self.input_bindings):
            raise ValueError('键盘与窗口已绑定')
        self.input_bindings.append((keyboard, target))

    def read(self, address):
        device = self.resolve_memory(address)
        return device.read(address) if device else 0xff

    def write(self, address, value):
        device = self.resolve_memory(address)
        if device: device.write(address, value)

    def resolve_memory(self, address):
        """Return the device currently selected by the CPU memory map."""
        return next((d for d in self.memory if d.contains(address)), None)

    def attach_io(self, name, device, ports):
        ports = tuple(ports)
        if any(device is component for component in self.components):
            raise ValueError('同一部件实例不能重复挂载')
        if len(set(ports)) != len(ports) or any(not 0 <= p <= 0xffff or p in self.ports for p in ports):
            raise ValueError(f'{name}: I/O 地址冲突或无效')
        used = {component.name for component in self.components}
        original = name
        index = 2
        while name in used:
            name = f'{original} ({index})'; index += 1
        device.name = name
        for port in ports: self.ports[port] = device
        self.components.append(device)
        if ports and not getattr(device, 'batch_io_safe', False): self._batch_unsafe_io = True
        if callable(getattr(device, 'tick', None)): self._clocked_devices.append(device)
        if callable(getattr(device, 'candidate', None)): self._daisy_devices.append(device)
        if callable(getattr(device, 'reti', None)): self._reti_devices.append(device)
        if callable(getattr(device, 'irq_active', None)): self._irq_sources.append(device)
        if callable(getattr(device, 'reset', None)): self._reset_devices.append(device)

    def attach_decoded_io(self, name, device, base, mask, count=1):
        """Decode selected address bits, including mirrors in the other bits."""
        if not 0 <= mask <= 0xffff or not 0 <= base <= 0xffff or count < 1:
            raise ValueError('无效的 I/O 译码')
        decoded = set(range(base, base + count))
        if any(value > 0xffff or value & mask != value for value in decoded):
            raise ValueError('基地址包含未译码位或超出范围')
        addresses = [a for a in range(65536) if a & mask in decoded]
        self.attach_io(name, device, addresses)

    def interrupt_candidate(self):
        for device in self._daisy_devices:
            candidate = device.candidate()
            if candidate is not None: return device, candidate
            if device.in_service(): break
        return None

    def acknowledge(self):
        candidate = self.interrupt_candidate()
        return candidate[0].acknowledge(candidate[1]) if candidate else 0xff

    def reti(self):
        for device in self._reti_devices:
            if device.reti(): break

    def io_read(self, address):
        if self._batch_active: self._sync_batch()
        device = self.ports.get(address)
        value = device.read_port(address) & 255 if device else 0xff
        self.io_history[address] = ('读', value)
        self.io_counts[address] = self.io_counts.get(address, 0) + 1
        low = address & 0xff
        self.io_low_history[low] = ('读', value, address)
        self.io_low_counts[low] = self.io_low_counts.get(low, 0) + 1
        if self._batch_active: self._adjust_batch_limit()
        return value

    def io_write(self, address, value):
        if self._batch_active: self._sync_batch()
        device = self.ports.get(address)
        if device: device.write_port(address, value)
        self.io_history[address] = ('写', value)
        self.io_counts[address] = self.io_counts.get(address, 0) + 1
        low = address & 0xff
        self.io_low_history[low] = ('写', value, address)
        self.io_low_counts[low] = self.io_low_counts.get(low, 0) + 1
        if self._batch_active: self._adjust_batch_limit()

    def _sync_batch(self):
        cycles = self.cpu.cpu.cycles
        elapsed = cycles - self._batch_synced
        if elapsed > 0:
            for device in self._clocked_devices: device.tick(elapsed)
            self._batch_synced = cycles

    def _can_batch(self):
        return (self.allow_batched_execution and not self._daisy_devices and not self._batch_unsafe_io
                and all(getattr(device, 'batch_tick_safe', False) for device in self._clocked_devices)
                and all(callable(getattr(device, 'batch_irq_deadline', None))
                        for device in self._irq_sources))

    def run_for(self, cycles):
        """Run a bounded slice; synchronize timers before each I/O instruction."""
        if cycles <= 0: return 0
        if not self._can_batch(): return self.step()
        self._batch_irq_level = any(device.irq_active() for device in self._irq_sources)
        self.cpu.set_interrupt(self._batch_irq_level)
        for device in self._irq_sources:
            deadline = device.batch_irq_deadline()
            if deadline is not None: cycles = min(cycles, max(1, deadline))
        self._batch_synced = 0
        self._batch_active = True
        try:
            elapsed = self.cpu.run(cycles)
            self._sync_batch()
        finally:
            self._batch_active = False
        self.cycles += elapsed
        return elapsed

    def _adjust_batch_limit(self):
        # An I/O operation can change the IRQ line or start a shorter timer.
        if any(device.irq_active() for device in self._irq_sources) != self._batch_irq_level:
            self.cpu.cpu.cycle_limit = 0
            return
        limit = self.cpu.cpu.cycle_limit
        for device in self._irq_sources:
            deadline = device.batch_irq_deadline()
            if deadline is not None: limit = min(limit, self.cpu.cpu.cycles + max(1, deadline))
        self.cpu.cpu.cycle_limit = limit

    def step(self):
        irq = self.interrupt_candidate() is not None or any(d.irq_active() for d in self._irq_sources)
        self.cpu.set_interrupt(irq)
        elapsed = self.cpu.step()
        self.cycles += elapsed
        for device in self._clocked_devices: device.tick(elapsed)
        return elapsed

    def reset(self):
        self.cpu.reset()
        self.cycles = 0
        self.io_history.clear()
        self.io_counts.clear()
        self.io_low_history.clear()
        self.io_low_counts.clear()
        for device in self._reset_devices: device.reset()
