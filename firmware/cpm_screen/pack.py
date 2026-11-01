"""Build a new physical CF image from the original CP/M disk and this BIOS."""
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
sys.path.insert(0, str(PLATFORM))
from firmware.cpm_screen.cpm_image import create_cf_image

def main():
    original = PLATFORM / 'reference/source/build/cpm/8mb-hd.dsk'
    logical = HERE / 'cpm-screen-logical.dsk'
    physical = HERE / 'cpm-screen-cf.img'
    if logical.exists() or physical.exists():
        raise FileExistsError('输出镜像已存在；请先移走旧镜像以避免覆盖')
    system = (HERE / 'source/cpm__.bin').read_bytes()
    if len(system) > 2 * 64 * 128: raise ValueError('CP/M 系统超出保留磁道')
    shutil.copyfile(original, logical)
    with logical.open('r+b') as out: out.write(system)
    create_cf_image(logical, physical)
    shutil.copyfile(HERE / 'source/loader.bin', HERE / 'loader.bin')

if __name__ == '__main__': main()
