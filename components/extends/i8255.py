"""Intel 8255 PPI mode 0 and bit set/reset, with independent pin callbacks.

Mode 1/2 handshaking is not implemented.  Inputs default high when unconnected.
"""

class I8255:
    batch_io_safe = True
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{f'P{port}{i}': 'bidirectional' for port in 'ABC' for i in range(8)},
            '/CS': 'input', '/RD': 'input', '/WR': 'input', 'A0': 'input', 'A1': 'input', 'RESET': 'input'}

    def __init__(self, base=0, read=None, write=None):
        self.base = base
        self.read_pins = read or (lambda port: 0xff)
        self.write_pins = write or (lambda port, value: None)
        self.reset()

    def reset(self):
        self.control = 0x9b
        self.latch = [0, 0, 0]

    def _output_mask(self, port):
        if port == 0: return 0 if self.control & 0x10 else 0xff
        if port == 1: return 0 if self.control & 0x02 else 0xff
        return (0 if self.control & 0x08 else 0xf0) | (0 if self.control & 0x01 else 0x0f)

    def read_port(self, address):
        port = (address - self.base) & 3
        if port == 3: return 0xff
        mask = self._output_mask(port)
        return (self.latch[port] & mask) | (self.read_pins(port) & ~mask & 0xff)

    def write_port(self, address, value):
        port, value = (address - self.base) & 3, value & 0xff
        if port < 3:
            self.latch[port] = value
            mask = self._output_mask(port)
            if mask: self.write_pins(port, value & mask)
        elif value & 0x80:
            if value & 0x64:
                raise NotImplementedError('8255 modes 1 and 2 are not implemented')
            self.control = value
            self.latch[:] = [0, 0, 0]
            for i in range(3):
                if self._output_mask(i): self.write_pins(i, 0)
        else:
            bit = (value >> 1) & 7
            self.latch[2] = (self.latch[2] & ~(1 << bit)) | ((value & 1) << bit)
            mask = self._output_mask(2)
            if mask: self.write_pins(2, self.latch[2] & mask)
