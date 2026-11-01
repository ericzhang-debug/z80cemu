"""End-to-end boot of the original author's ROM and disk, when built locally."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boards.z80v2 import Z80V2

class CPMBootTests(unittest.TestCase):
    def test_original_cpm_dir(self):
        build = Path(__file__).resolve().parents[1] / 'reference/source/build/cpm'
        rom, disk = build/'loader.bin', build/'cf-cpm.img'
        if not rom.exists() or not disk.exists(): self.skipTest('原始固件或 CF 测试镜像尚未构建')
        board = Z80V2(cf_image=disk, readonly=True)
        board.rom.load(rom.read_bytes())
        serial = board.ports[0x3e]
        for _ in range(1800000):
            board.step()
            if bytes(serial.output).endswith(b'a>'): break
        else: self.fail(f'CP/M 启动超时 PC={board.cpu.cpu.pc:04X}, output={bytes(serial.output)!r}')
        # The ACIA has only one receive register; pace terminal input like typing.
        for char in b'DIR':
            serial.send(bytes([char]))
            for _ in range(10000):
                board.step()
                if bytes(serial.output).endswith(bytes([char])): break
            else: self.fail(f'未收到字符回显: {char:02x}')
        serial.send(b'\r')
        for _ in range(800000):
            board.step()
            if b'ASM      COM' in bytes(serial.output) and bytes(serial.output).endswith(b'a>'): break
        else: self.fail(f'DIR 命令超时 PC={board.cpu.cpu.pc:04X}, output={bytes(serial.output)!r}')
        self.assertIn(b'MBASIC   COM', bytes(serial.output))
