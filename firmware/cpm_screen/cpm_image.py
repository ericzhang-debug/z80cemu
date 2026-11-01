"""Convert the project's 128-byte CP/M sectors into 512-byte CF sectors."""
import argparse
from pathlib import Path

def create_cf_image(source, destination, sectors=65536):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve(): raise ValueError('源文件和目标文件不能相同')
    if source.stat().st_size % 128: raise ValueError('CP/M 镜像长度必须是 128 的倍数')
    if source.stat().st_size // 128 > sectors: raise ValueError('目标容量不足')
    # Exclusive creation prevents an existing disk image being silently overwritten.
    with source.open('rb') as inp, destination.open('xb') as out:
        while True:
            chunk = inp.read(128)
            if not chunk: break
            out.write(chunk + bytes(384))
        out.truncate(sectors * 512)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination')
    args = parser.parse_args(); create_cf_image(args.source, args.destination)
