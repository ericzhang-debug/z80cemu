"""Example of wiring CTC ZC/TO0 to the PIO A strobe in Python."""
from platform_core import Machine
from components.extends.z80_ctc import Z80CTC
from components.extends.z80_pio import Z80PIO

CLOCK_HZ = 1_000_000
MEMORY = [
    {'name': 'ROM', 'type': 'rom', 'start': 0x0000, 'size': 0x2000},
    {'name': 'RAM', 'type': 'ram', 'start': 0x2000, 'size': 0xe000},
]

def build():
    machine = Machine({'memory': MEMORY})
    pio = Z80PIO(0x14)
    def output_pulse(channel, count):
        if channel == 0:
            for _ in range(count):
                pio.ports[0].set_strobe(False)
                pio.ports[0].set_strobe(True)
    ctc = Z80CTC(0x10, pulse=output_pulse)
    machine.attach_decoded_io('CTC', ctc, 0x10, 0xff, 4)
    machine.attach_decoded_io('PIO', pio, 0x14, 0xff, 4)
    return machine, CLOCK_HZ
