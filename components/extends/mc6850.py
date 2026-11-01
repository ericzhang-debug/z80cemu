"""MC6850 register-level ACIA with clocked character transfers.

External serial is presented as characters rather than pin waveforms.  See
``set_modem_inputs`` and ``receive_byte`` for modem and error injection.
"""
from collections import deque


class MC6850:
    gui_resizable = True
    def bind_ui(self, root, pause): self._ui_active = True
    def close_ui(self): self._ui_active = False
    def open_gui(self, root, pause):
        from ui.component_views import serial_window
        return serial_window(root, self, pause)
    batch_tick_safe = True
    batch_io_safe = True
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{p: 'input' for p in ('E', 'R/W', 'RS', 'CS0', 'CS1', '/CS2', 'RxC', 'TxC', 'RxD', '/CTS', '/DCD')},
            **{p: 'output' for p in ('TxD', '/RTS', '/IRQ')}}

    def __init__(self, base, cpu_hz=1_000_000, baud=9600):
        if cpu_hz <= 0 or baud <= 0: raise ValueError('时钟和波特率必须为正数')
        self.base, self.cpu_hz, self.baud = base, cpu_hz, baud
        # A transcript belongs to the device, not to a particular window.
        # Clear explicitly on platform reset or when the user requests it.
        self.output = bytearray()
        self.output_generation = 0
        # Logic levels of active-low modem inputs, not their asserted state.
        self.cts = 0
        self.dcd = 0
        self.reset()

    def clear_output(self):
        self.output.clear()
        self.output_generation += 1

    def reset(self):
        self.control = 0
        self.receive = None
        self.framing_error = False
        self.parity_error = False
        self.overrun = False
        self._overrun_pending = False
        self._dcd_latched = bool(self.dcd)
        self._dcd_irq = False
        self._status_seen = False
        self._tdr = None
        self._tx_shift = None
        self.tx_remaining = 0
        self._start_remaining = 0
        self.rx_queue = deque()
        self.rx_remaining = 0

    @property
    def tx(self):
        """Currently transmitting byte (or the byte waiting in TDR)."""
        return self._tx_shift if self._tx_shift is not None else self._tdr

    @property
    def rts(self):
        """Logical level of /RTS; CR6:CR5=10 deasserts RTS."""
        return int((self.control & 0x60) == 0x40)

    @property
    def break_active(self):
        return (self.control & 0x60) == 0x60

    @property
    def divider(self):
        return (1, 16, 64, 1)[self.control & 3]

    def frame_cycles(self):
        bits = (11, 11, 10, 10, 11, 10, 11, 11)[(self.control >> 2) & 7]
        return max(1, round(self.cpu_hz * bits / self.baud))

    def bit_cycles(self):
        return max(1, round(self.cpu_hz / self.baud))

    def set_modem_inputs(self, *, cts=None, dcd=None):
        if cts is not None:
            if cts not in (0, 1): raise ValueError('CTS must be 0 or 1')
            self.cts = cts
        if dcd is not None:
            if dcd not in (0, 1): raise ValueError('DCD must be 0 or 1')
            if dcd and not self.dcd:
                self._dcd_latched = True
                self._dcd_irq = True
                self.receive = None
                self.framing_error = self.parity_error = False
            self.dcd = dcd

    def irq_active(self):
        rx_irq = bool(self.control & 0x80) and (self.receive is not None or self._overrun_pending or self.overrun or self._dcd_irq)
        tx_irq = (self.control & 0x60) == 0x20 and self._tdr is None and not self.cts
        return rx_irq or tx_irq

    def batch_irq_deadline(self):
        """Cycles until a currently inactive interrupt can become active."""
        if self.irq_active(): return None
        deadlines = []
        if self.control & 0x80 and self.rx_queue:
            deadlines.append(self.rx_remaining or self.frame_cycles())
        if (self.control & 0x60) == 0x20 and self._tdr is not None and not self.cts and not self.break_active:
            deadlines.append(self.tx_remaining if self._tx_shift is not None else (self._start_remaining or 1))
        return min(deadlines) if deadlines else None

    def status(self):
        return ((1 if self.receive is not None or self.overrun else 0)
                | (2 if self._tdr is None and not self.cts else 0)
                | (4 if self._dcd_latched or self.dcd else 0)
                | (8 if self.cts else 0)
                | (0x10 if self.framing_error else 0)
                | (0x20 if self.overrun else 0)
                | (0x40 if self.parity_error else 0)
                | (0x80 if self.irq_active() else 0))

    def read_port(self, address):
        if not (address - self.base) & 1:
            self._status_seen = True
            return self.status()
        value = self.receive if self.receive is not None else 0
        self.receive = None
        self.framing_error = self.parity_error = False
        if self._overrun_pending:
            self.overrun = True
            self._overrun_pending = False
        elif self.overrun and self._status_seen:
            self.overrun = False
        if self._status_seen:
            self._dcd_irq = False
            self._dcd_latched = bool(self.dcd)
        self._status_seen = False
        return value

    def write_port(self, address, value):
        if not (address - self.base) & 1:
            if value & 3 == 3: self.reset()
            else: self.control = value & 0xff
        else:
            # Software is expected to check TDRE; an early write replaces TDR.
            self._tdr = value & (0x7f if ((self.control >> 2) & 7) < 4 else 0xff)
            if self._tx_shift is None and self._start_remaining == 0:
                self._start_remaining = self.bit_cycles()

    def receive_byte(self, value, *, framing_error=False, parity_error=False):
        """Queue one received character and optional line error indications."""
        self.rx_queue.append((value & 0xff, bool(framing_error), bool(parity_error)))

    def send(self, data):
        for value in data: self.receive_byte(value)

    def _tx_tick(self, cycles):
        remaining = cycles
        while remaining > 0:
            if self._tx_shift is not None:
                spent = min(remaining, self.tx_remaining)
                remaining -= spent; self.tx_remaining -= spent
                if self.tx_remaining: break
                self.output.append(self._tx_shift)
                self._tx_shift = None
                self._start_remaining = 0
            if self._tdr is None or self.cts or self.break_active: break
            if self._start_remaining:
                spent = min(remaining, self._start_remaining)
                remaining -= spent; self._start_remaining -= spent
                if self._start_remaining: break
            self._tx_shift, self._tdr = self._tdr, None
            self.tx_remaining = self.frame_cycles()

    def tick(self, cycles):
        if cycles < 0: raise ValueError('cycles must not be negative')
        self._tx_tick(cycles)
        remaining = cycles
        while self.rx_queue and remaining > 0:
            if not self.rx_remaining: self.rx_remaining = self.frame_cycles()
            spent = min(remaining, self.rx_remaining)
            self.rx_remaining -= spent; remaining -= spent
            if not self.rx_remaining:
                value, framing, parity = self.rx_queue.popleft()
                if self.dcd: continue
                if self.receive is not None or self.overrun:
                    self._overrun_pending = True
                else:
                    self.receive = value & (0x7f if ((self.control >> 2) & 7) < 4 else 0xff)
                    self.framing_error = framing
                    self.parity_error = parity
