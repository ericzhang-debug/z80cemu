"""Laser 310 example: memory map and explicit peripheral wiring."""
from pathlib import Path
from boards.laser310 import Laser310Machine
from components.extends.mc6847 import MC6847
from components.extends.vtech_keyboard import VTechKeyboard
from components.extends.vtech_cassette import VTechCassette
from components.extends.two_bit_speaker import TwoBitSpeaker
from components.extends.vtech_printer import VTechPrinter

CLOCK_HZ = 3_546_894
FIRMWARE_DIR = Path(__file__).resolve().parents[1] / 'firmware' / 'laser310'
MEMORY = [
    {'name': 'Laser 310 BASIC ROM', 'type': 'rom', 'start': 0, 'size': 0x4000},
    {'name': '视频 RAM', 'type': 'ram', 'start': 0x7000, 'size': 0x800},
    {'name': '用户 RAM', 'type': 'ram', 'start': 0x7800, 'size': 0x4000},
]


def build():
    machine = Laser310Machine(MEMORY, CLOCK_HZ)
    image = (FIRMWARE_DIR / 'vtechv20.u12').read_bytes()
    if len(image) != 0x4000: raise ValueError('Laser 310 BASIC ROM 应为 16 KiB')
    machine.memory[0].load(image)
    screen = MC6847(machine.memory[1].data, (FIRMWARE_DIR / 'vtech1.chr').read_bytes())
    keyboard = VTechKeyboard()
    cassette = VTechCassette(machine.now_cycles, CLOCK_HZ)
    speaker = TwoBitSpeaker(machine.now_cycles, CLOCK_HZ)
    printer = VTechPrinter()
    machine.screen, machine.keyboard, machine.cassette = screen, keyboard, cassette
    machine.speaker = speaker
    machine.printer = printer
    machine.attach_io('MC6847 视频', screen, [])
    machine.attach_io('Laser 310 键盘', keyboard, [])
    machine.attach_io('Laser 310 磁带', cassette, [])
    machine.attach_io('双线扬声器', speaker, [])
    machine.attach_io('Laser 310 打印机', printer,
                      (address for address in range(65536) if address & 0xff in (0x00, 0x0d, 0x0e)))
    machine.bind_keyboard(keyboard, screen)
    machine.auto_open_windows = ['MC6847 视频', 'Laser 310 打印机']
    return machine, CLOCK_HZ
