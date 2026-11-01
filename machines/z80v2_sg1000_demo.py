"""Z80-V2 sample using the self-authored SG-1000 display test ROM."""
from pathlib import Path
from boards.z80v2 import Z80V2

HERE = Path(__file__).resolve().parents[1]

def build():
    machine = Z80V2(4_000_000)
    machine.rom.load((HERE / 'firmware/sg1000/sg1000_demo.bin').read_bytes())
    return machine, 4_000_000
