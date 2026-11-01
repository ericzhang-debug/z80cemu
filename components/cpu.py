"""Adapter to the bundled redcode Z80 core."""
import ctypes as C
from pathlib import Path
from .cpu_layout import CPU, READ, WRITE
NOTIFY = C.CFUNCTYPE(None, C.c_void_p)

class Z80:
    name = 'Z80 CPU'
    pins = {**{f'A{i}': 'output' for i in range(16)},
            **{f'D{i}': 'bidirectional' for i in range(8)},
            **{p: 'output' for p in ('/M1', '/MREQ', '/IORQ', '/RD', '/WR', '/RFSH', '/HALT', '/BUSACK')},
            **{p: 'input' for p in ('CLK', '/RESET', '/WAIT', '/INT', '/NMI', '/BUSREQ')}}

    def __init__(self, bus, dll=None):
        self.cpu = CPU()
        path = Path(dll) if dll else Path(__file__).resolve().parents[1] / 'lib/bin/Z80.dll'
        self.lib = C.CDLL(str(path))
        ptr = C.POINTER(CPU)
        self.lib.z80_power.argtypes = [ptr, C.c_int]
        self.lib.z80_instant_reset.argtypes = [ptr]
        self.lib.z80_int.argtypes = [ptr, C.c_int]
        self.lib.z80_nmi.argtypes = [ptr]
        for name in ('z80_power', 'z80_instant_reset', 'z80_int', 'z80_nmi'):
            getattr(self.lib, name).restype = None
        self.lib.z80_run.argtypes = [ptr, C.c_size_t]
        self.lib.z80_run.restype = C.c_size_t
        self.callback_error = None
        def guard(fn, fallback=None):
            def call(*args):
                if self.callback_error is not None: return fallback
                try: return fn(*args)
                except Exception as error:
                    self.callback_error = error
                    self.cpu.cycle_limit = 0
                    return fallback
            return call
        self.callbacks = [READ(guard(lambda _, a: bus.read(a), 0xff)), WRITE(guard(lambda _, a, v: bus.write(a, v))),
                          READ(guard(lambda _, a: bus.io_read(a), 0xff)), WRITE(guard(lambda _, a, v: bus.io_write(a, v))),
                          READ(guard(lambda _, a: bus.acknowledge(), 0xff)), NOTIFY(guard(lambda _: bus.reti()))]
        for field in ('fetch_opcode', 'fetch', 'read', 'nop'):
            setattr(self.cpu, field, C.cast(self.callbacks[0], C.c_void_p).value)
        for field, cb in zip(('write', 'in_', 'out', 'inta', 'reti'), self.callbacks[1:]):
            setattr(self.cpu, field, C.cast(cb, C.c_void_p).value)
        self.lib.z80_power(C.byref(self.cpu), 1)
        self._interrupt_active = None

    def step(self):
        return self.run(1)

    def run(self, budget):
        self.callback_error = None
        elapsed = self.lib.z80_run(C.byref(self.cpu), budget)
        if self.callback_error is not None:
            error, self.callback_error = self.callback_error, None
            raise RuntimeError('CPU 总线回调失败；当前指令可能已部分执行') from error
        return elapsed

    def reset(self):
        self.lib.z80_instant_reset(C.byref(self.cpu))
        self._interrupt_active = None

    def set_interrupt(self, active):
        active = bool(active)
        if self._interrupt_active != active:
            self.lib.z80_int(C.byref(self.cpu), int(active))
            self._interrupt_active = active

    def nmi(self):
        self.lib.z80_nmi(C.byref(self.cpu))
