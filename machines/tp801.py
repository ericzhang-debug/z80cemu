"""TP801: explicit component assembly, bus decoding and signal wiring."""
from pathlib import Path
from boards.tp801 import TP801Machine
from components.extends.z80_ctc import Z80CTC
from components.extends.z80_pio import Z80PIO
from components.extends.tp801_keypad import TP801Keypad
from components.extends.tp801_display import TP801Display
from components.extends.tp801_cassette import TP801Cassette
from components.extends.tp801_prom import PROMChip, TP801PROMProgrammer

CLOCK_HZ = 1_996_800
FIRMWARE = Path(__file__).resolve().parents[1] / 'firmware'/'tp801' / 'TPBUG.BIN'
MEMORY = [
    {'name': 'TPBUG ROM', 'type': 'rom', 'start': 0x0000, 'size': 0x0800},
    {'name': 'RAM', 'type': 'ram', 'start': 0x2000, 'size': 0x1000},
]

class OutputLatch:
    """I/O decoder forwards writes to board-wired signal consumers."""
    def __init__(self, callback): self.callback = callback
    def read_port(self, address): return 0xff
    def write_port(self, address, value): self.callback(value)

def build():
    machine = TP801Machine(MEMORY)
    firmware = FIRMWARE.read_bytes()
    if len(firmware) != 0x800: raise ValueError('TPBUG 固件必须是 2048 字节')
    machine.memory[0].load(firmware)
    prom1, prom2 = PROMChip('PROM1', 0x0800), PROMChip('PROM2', 0x1000)
    machine.memory.extend((prom1, prom2)); machine.components.extend((prom1, prom2))
    machine.rebuild_memory_cache()
    programmer = TP801PROMProgrammer(prom1, prom2)
    programmer.read_byte = machine.read
    machine.prom = programmer

    def ctc_pulse(channel, count):
        if channel == 2:
            if programmer.program_enable: programmer.pulse(count)
            else: machine.cpu.nmi()
    ctc = Z80CTC(0x84, ctc_pulse); machine.ctc = ctc
    pio = Z80PIO(0x80)
    display = TP801Display()

    def write_batch(image):
        operations = []
        for address, value in image.items():
            device = machine.resolve_memory(address)
            if device is None or device.readonly: raise ValueError(f'{address:04X} 不是可写 RAM')
            operations.append((device, address, value))
        for device, address, value in operations: device.write(address, value)

    def tape_range():
        return ((machine.read(0x2fc0) << 8) | machine.read(0x2fc1),
                (machine.read(0x2fc2) << 8) | machine.read(0x2fc3))
    cassette = TP801Cassette(machine.read, write_batch, tape_range)
    intercepted = {}
    def key_press(row, col):
        if (row, col) in ((2, 0), (3, 0)): ctc.core.trigger(2)
        if machine.cpu.cpu.pc < 0x800 and machine.read(0x2fff) == 0x12:
            action = {(4, 2): cassette.request_save, (4, 1): cassette.request_load}.get((row, col))
            if action is not None:
                intercepted[(row, col)] = action
                return False
        if machine.cpu.cpu.pc < 0x800 and machine.read(0x2fff) == 0x11 and (row, col) == (5, 4):
            intercepted[(row, col)] = programmer.request_program
            return False
    def key_release(row, col):
        action = intercepted.pop((row, col), None)
        if action is not None: action()
    keypad = TP801Keypad(key_press, key_release, lambda: programmer.s2_prom_boot)

    def digit_write(value):
        display.set_digits(value); keypad.set_rows(value); programmer.set_enable(value & 0x80)

    # Order is the Z80 daisy-chain priority: CTC before PIO.
    machine.attach_decoded_io('Z80 CTC', ctc, 0x84, 0xff, 4)
    machine.attach_decoded_io('Z80 PIO', pio, 0x80, 0xff, 4)
    machine.attach_decoded_io('数码管段选锁存器', OutputLatch(display.set_segments), 0x88, 0xff, 4)
    machine.attach_decoded_io('数码管位选锁存器', OutputLatch(digit_write), 0x8c, 0xff, 4)
    machine.attach_decoded_io('TP801 矩阵键盘', keypad, 0x90, 0xff, 4)
    machine.attach_io('TP801 数码管', display, [])
    machine.attach_io('TP801 磁带', cassette, [])
    machine.attach_io('TP801 PROM 编程器', programmer, [])
    # Named handles are convenient for experiments and integration tests.
    machine.keypad, machine.display, machine.cassette = keypad, display, cassette
    machine.pio = pio
    return machine, CLOCK_HZ
