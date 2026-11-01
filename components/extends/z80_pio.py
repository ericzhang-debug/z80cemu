"""Z80 PIO component."""
class PIOPort:
    def __init__(self, index=0):
        self.index = index; self.peer = None
        self.mode = 1; self.latch = 0; self.inputs = 0xff
        self.direction = 0xff; self.vector = 0
        self.interrupt_enabled = False; self.mask = 0xff
        self.control = 0; self.expect = None; self.pending = False; self.in_service = False
        self.input_latch = 0xff; self.ready = True; self.strobe = True
        self.condition = False
    def write_control(self, value):
        if self.expect == 'direction': self.direction = value; self.expect = None; self.evaluate()
        elif self.expect == 'mask': self.mask = value; self.expect = None; self.evaluate()
        elif not value & 1: self.vector = value
        elif value & 0x0f == 0x0f:
            mode = value >> 6
            if mode == 2 and self.index == 1:
                return  # Mode 2 exists on port A only.
            self.mode = mode; self.pending = False; self.condition = False
            if not (self.index == 1 and self.peer is not None and self.peer.mode == 2):
                self.ready = self.mode == 1
            if self.mode == 2 and self.peer is not None: self.peer.ready = True
            if self.mode == 3: self.expect = 'direction'
        elif value & 0x0f == 7:
            self.control = value; self.interrupt_enabled = bool(value & 0x80)
            if value & 0x10: self.expect = 'mask'
            if not self.interrupt_enabled: self.pending = False; self.condition = False
            elif self.expect != 'mask': self.evaluate()
        elif value & 0x0f == 3:
            self.interrupt_enabled = bool(value & 0x80)
            if not self.interrupt_enabled: self.pending = False; self.condition = False
            else: self.evaluate()
    def read(self):
        result = self.peek()
        if self.mode == 1: self.ready = True
        elif self.mode == 2 and self.peer is not None: self.peer.ready = True
        return result
    def peek(self):
        if self.mode == 0: return self.latch
        if self.mode == 3: return (self.inputs & self.direction) | (self.latch & ~self.direction & 255)
        return self.input_latch
    def write(self, value):
        self.latch = value & 0xff
        if self.mode in (0, 2): self.ready = True
        if self.mode == 3: self.evaluate()
    def output_pins(self):
        """Return (driven-bit mask, output values) for the external data pins."""
        if self.mode == 0: mask = 0xff
        elif self.mode == 2: mask = 0xff if not self.strobe else 0
        elif self.mode == 3: mask = ~self.direction & 0xff
        else: mask = 0
        return mask, self.latch & mask
    def set_inputs(self, value):
        self.inputs = value & 0xff
        self.evaluate()
    def set_strobe(self, level):
        level = bool(level); previous = self.strobe; self.strobe = level
        if previous == level: return
        bidirectional_input = self.index == 1 and self.peer is not None and self.peer.mode == 2
        if self.mode == 3 and not bidirectional_input: return
        target = self.peer if bidirectional_input else self
        input_transfer = bidirectional_input or self.mode == 1
        if not level and input_transfer:
            target.input_latch = target.inputs
        elif level:
            self.ready = False
            if self.interrupt_enabled: self.pending = True
    def evaluate(self):
        if self.mode != 3 or not self.interrupt_enabled or self.expect is not None: return
        bits = (~self.mask) & self.direction & 255
        active = self.inputs if self.control & 0x20 else ~self.inputs
        matched = (active & bits) == bits if self.control & 0x40 else bool(active & bits)
        if bits and matched and not self.condition: self.pending = True
        self.condition = bool(bits and matched)


class Z80PIO:
    def open_gui(self, root, pause):
        from ui.component_views import device_window
        return device_window(root, self, pause)
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{f'P{p}{i}': 'bidirectional' for p in 'AB' for i in range(8)},
            **{n: 'input' for n in ('CLK', '/CE', '/IORQ', '/RD', '/M1', 'IEI', 'B/A', 'C/D', '/ASTB', '/BSTB')},
            **{n: 'output' for n in ('IEO', '/INT', 'ARDY', 'BRDY')}}

    def __init__(self, base): self.base = base; self.reset()
    def reset(self):
        self.ports = [PIOPort(0), PIOPort(1)]
        self.ports[0].peer, self.ports[1].peer = self.ports[1], self.ports[0]
    def read_port(self, address):
        offset = (address - self.base) & 3
        return self.ports[offset & 1].read() if offset < 2 else 0xff
    def write_port(self, address, value):
        offset = (address - self.base) & 3
        port = self.ports[offset & 1]
        if offset < 2: port.write(value)
        else: port.write_control(value)
    def candidate(self):
        for i, port in enumerate(self.ports):
            if port.in_service: return None
            if port.pending: return i
        return None
    def acknowledge(self, candidate):
        port = self.ports[candidate]; port.pending = False; port.in_service = True
        return port.vector
    def reti(self):
        for port in self.ports:
            if port.in_service: port.in_service = False; return True
        return False
    def in_service(self): return self.ports[0].in_service or self.ports[1].in_service
