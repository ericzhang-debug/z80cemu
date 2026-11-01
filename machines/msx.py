"""MSX1 sample: explicit memory slots, I/O decoding and signal connections."""
from pathlib import Path
from boards.msx import MSX1
from components.extends.i8255 import I8255
from components.extends.msx_keyboard import MSXKeyboard
from components.extends.msx_cartridge import MSXCartridge
from components.extends.ay_3_8910 import AY38910
from components.extends.tms9918a import TMS9918A
from components.extends.joypad import Joypads
from components.extends.msx_cassette import MSXCassette

CLOCK_HZ = 3_579_545
FIRMWARE = Path(__file__).resolve().parents[1] / 'firmware' / 'msx'

def build_with_firmware(main_rom, logo_rom=None):
    machine = MSX1()
    machine.bios.name = Path(main_rom).stem
    machine.bios.load(Path(main_rom).read_bytes())
    machine.logo.name = Path(logo_rom).stem if logo_rom else '空扩展 ROM'
    if logo_rom: machine.logo.load(Path(logo_rom).read_bytes())
    keyboard = MSXKeyboard()
    cassette = MSXCassette(cpu_hz=CLOCK_HZ)
    row = [0]
    def read_pins(port): return keyboard.read_row(row[0]) if port == 1 else 0xff
    def write_pins(port, value):
        if port == 0: machine.slots = value
        elif port == 2:
            row[0] = value & 15
            cassette.set_pins(not (value & 0x10), bool(value & 0x20))
    ppi = I8255(0xa8, read_pins, write_pins)
    machine.attach_decoded_io('Intel 8255 PPI', ppi, 0xa8, 0xff, 4)
    machine.attach_io('MSX 矩阵键盘', keyboard, [])
    video = TMS9918A(0x98, CLOCK_HZ)
    machine.attach_decoded_io('TMS9918A 显卡', video, 0x98, 0xff, 2)
    machine.bind_keyboard(keyboard, video)
    pads = Joypads()
    def psg_input():
        player = 1 if psg.registers[15] & 0x40 else 0
        return (cassette.read_level() << 7) | sum((button not in pads.pressed[player]) << bit
                                                 for bit, button in enumerate(pads.buttons))
    psg = AY38910(cpu_hz=CLOCK_HZ, read_a=psg_input)
    machine.attach_decoded_io('AY-3-8910 声音', psg, 0xa0, 0xff, 3)
    machine.attach_io('MSX 游戏控制器', pads, [])
    machine.attach_io('MSX 磁带机', cassette, [])
    cartridge = MSXCartridge(machine.reset)
    machine.cartridge = cartridge
    machine.attach_io('MSX 卡带', cartridge, [])
    machine.auto_open_windows = ['TMS9918A 显卡', 'MSX 游戏控制器', 'MSX 卡带']
    return machine, CLOCK_HZ

def build():
    return build_with_firmware(FIRMWARE / 'rainbios' / 'rainbios_msx1.rom')
