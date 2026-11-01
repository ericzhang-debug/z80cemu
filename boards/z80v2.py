"""Bitrowz Z80-V2 subset, based on the original GAL equations."""
from components.ram import RAM
from components.rom import ROM
from platform_core import Machine
from pathlib import Path
import json

class MemorySelect:
    batch_io_safe = True
    def __init__(self, board): self.board = board
    def write_port(self, address, value): self.board.all_ram = bool(address & 1)
    def read_port(self, address): return 0xff
    def reset(self): self.board.all_ram = False

class LEDs:
    batch_io_safe = True
    gui_kind = 'leds'
    def open_gui(self, root, pause):
        from ui.component_views import device_window
        return device_window(root, self, pause)
    def __init__(self): self.value = 0
    def reset(self): self.value = 0
    def write_port(self, address, value): self.value = value
    def read_port(self, address): return 0xff

class Z80V2(Machine):
    def __init__(self, clock_hz=4_000_000, cf_image=None, readonly=True, wire=None):
        super().__init__({'memory': []})
        self.allow_batched_execution = True
        self.rom = ROM('W27C512 ROM（低 32K 窗口）', 0, 0x8000)
        self.ram = RAM('RAM（64K）', 0, 0x10000)
        self.memory = [self.rom, self.ram]
        self.components.extend(self.memory)
        self.all_ram = False
        if wire is None:
            from machines.z80v2 import wire_board
            wire = wire_board
        wire(self, clock_hz, cf_image, readonly)

    def read(self, address):
        # This board maps both chips with offset zero; avoid repeated region
        # lookups on every opcode and operand fetch.
        return self.rom.data[address] if address < 0x8000 and not self.all_ram else self.ram.data[address]

    def resolve_memory(self, address):
        return self.rom if address < 0x8000 and not self.all_ram else self.ram

    def write(self, address, value):
        if address >= 0x8000 or self.all_ram: self.ram.data[address] = value & 255

def load_board_config(path, wire=None):
    path = Path(path)
    with path.open(encoding='utf-8') as f: config = json.load(f)
    clock = config.get('clock_hz', 4_000_000)
    if isinstance(clock, bool) or not isinstance(clock, int) or clock <= 0:
        raise ValueError('clock_hz 必须是正整数')
    def resolve(key):
        value = config.get(key)
        return (path.parent / value).resolve() if value else None
    readonly = config.get('cf_readonly', True)
    if not isinstance(readonly, bool): raise ValueError('cf_readonly 必须为 true 或 false')
    board = Z80V2(clock, resolve('cf_image'), readonly, wire)
    windows = config.get('open_windows')
    if windows is not None and (not isinstance(windows, list) or any(not isinstance(name, str) for name in windows)):
        raise ValueError('open_windows 必须是 null 或名称数组')
    board.auto_open_windows = windows
    rom = resolve('rom_image')
    if rom is not None: board.rom.load(rom.read_bytes())
    return board, clock
