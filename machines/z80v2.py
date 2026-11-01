"""Bitrowz Z80-V2 接线样例；复制并修改即可创建其他机器。"""
from pathlib import Path
from components.extends.mc6850 import MC6850
from components.extends.compact_flash import CompactFlash
from components.extends.tms9918a import TMS9918A
from components.extends.vt82c42 import VT82C42
from components.extends.joypad import Joypads
from components.extends.sn76489 import SN76489

CONFIG_PATH = Path(__file__).resolve().parent / 'z80v2_config.json'

def wire_board(machine, clock_hz, cf_image, readonly):
    """各部件及连接顺序；中断菊花链按添加顺序排序。"""
    from boards.z80v2 import MemorySelect, LEDs
    machine.attach_decoded_io('内存映射选择', MemorySelect(machine), 0, 0xff, 2)
    machine.attach_decoded_io('数字输出 LED', LEDs(), 2, 0xff)
    machine.attach_decoded_io('MC68B50 串口', MC6850(0x3e, clock_hz, 115200), 0x3e, 0xff, 2)
    keyboard = VT82C42(0x2e)
    video = TMS9918A(0xbe, clock_hz)
    machine.attach_decoded_io('VT82C42 键盘', keyboard, 0x2e, 0xff, 2)
    machine.attach_decoded_io('TMS9918A 显卡', video, 0xbe, 0xff, 2)
    machine.bind_keyboard(keyboard, video)
    machine.attach_decoded_io('SN76489 声卡', SN76489(cpu_hz=clock_hz), 0x7e, 0xff, 2)
    machine.attach_io('游戏控制器', Joypads(), [a for a in range(65536) if (a & 255) in (0xc0, 0xc1, 0xdc, 0xdd)])
    # Keep the slot present even when no card image is inserted.
    machine.attach_decoded_io('CF 卡', CompactFlash(0xf0, cf_image, readonly), 0xf0, 0xff, 8)

def build():
    from boards.z80v2 import load_board_config
    return load_board_config(CONFIG_PATH, wire=wire_board)
