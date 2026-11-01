"""Z80-V2 sample with the display-console CP/M image."""
from pathlib import Path
from boards.z80v2 import Z80V2

HERE = Path(__file__).resolve().parents[1]

def build():
    firmware = HERE / 'firmware/cpm_screen'
    machine = Z80V2(4_000_000, firmware / 'cpm-screen-cf.img', readonly=True)
    machine.rom.load((firmware / 'loader.bin').read_bytes())
    return machine, 4_000_000
