"""MSX1 assembly with the independent C-BIOS cartridge firmware."""
from machines.msx import FIRMWARE, build_with_firmware

def build():
    return build_with_firmware(FIRMWARE / 'cbios_main_msx1_eu.rom',
                               FIRMWARE / 'cbios_logo_msx1.rom')
