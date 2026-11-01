"""通用示例：复制此文件并编辑设备、端口和接线。"""
from platform_core import Machine
from components.extends.z80_ctc import Z80CTC
from components.extends.z80_pio import Z80PIO
from components.extends.mc6850 import MC6850

MEMORY = [
    {'name': 'ROM', 'type': 'rom', 'start': 0x0000, 'size': 0x2000},
    {'name': 'RAM', 'type': 'ram', 'start': 0x2000, 'size': 0xe000},
]
CLOCK_HZ = 1_000_000
# None: open all available component windows; []: open none; or list names.
OPEN_WINDOWS = None

def build():
    machine = Machine({'memory': MEMORY})
    machine.auto_open_windows = OPEN_WINDOWS
    ctc = Z80CTC(0x10)
    pio = Z80PIO(0x14)
    machine.attach_decoded_io('Z80 CTC', ctc, 0x10, 0xff, 4)
    machine.attach_decoded_io('Z80 PIO', pio, 0x14, 0xff, 4)
    machine.attach_decoded_io('MC68B50', MC6850(0x18, CLOCK_HZ), 0x18, 0xff, 2)
    # Example signal wiring: uncomment to route ZC/TO0 to CLK/TRG1.
    # ctc.core.connect(0, 1)
    return machine, CLOCK_HZ
