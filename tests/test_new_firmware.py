"""Exercise the supplied ROMs using the actual CPU and device ports."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines.z80v2_screen_cpm import build as screen_cpm
from machines.z80v2_sg1000_demo import build as sg1000

class FirmwareTests(unittest.TestCase):
    def test_sg1000_rom_initializes_and_displays_title(self):
        machine, _ = sg1000()
        for _ in range(10000): machine.step()
        vdp = machine.ports[0xbe]
        self.assertTrue(machine.cpu.cpu.halt_line)
        self.assertEqual(bytes(vdp.vram[0x1a0:0x1a7]), bytes([1, 2, 3, 4, 5, 5, 5]))
        self.assertEqual(set(vdp.render()), {4, 15})

    def test_screen_cpm_boots_with_batched_execution(self):
        machine, _ = screen_cpm()
        serial, video = machine.ports[0x3e], machine.ports[0xbe]
        for _ in range(500000):
            machine.run_for(2048)
            if bytes(serial.output).endswith(b'a>'): break
        else: self.fail('批量模式下 CP/M 启动超时')
        # Finish the prompt's pending VDP update.
        for _ in range(300): machine.run_for(2048)
        self.assertTrue(video.registers[1] & 0x40)
        self.assertIn(b'a>', bytes(video.vram[:960]))
        keyboard = machine.ports[0x2e]
        for key in ('d', 'i', 'r', 'Return'):
            for pressed in (True, False):
                keyboard.key_event(key, pressed)
                stop = machine.cycles + 50000
                while machine.cycles < stop: machine.run_for(min(2048, stop - machine.cycles))
        for _ in range(10000):
            machine.run_for(2048)
            if b'MBASIC   COM' in serial.output and bytes(serial.output).endswith(b'a>'): break
        else: self.fail(f'批量模式下键盘 DIR 失败: {bytes(serial.output)[-300:]!r}')

    def test_screen_cpm_boot_and_keyboard_dir(self):
        machine, _ = screen_cpm()
        serial, vdp, keyboard = machine.ports[0x3e], machine.ports[0xbe], machine.ports[0x2e]
        for _ in range(1800000):
            machine.step()
            if bytes(serial.output).endswith(b'a>'): break
        else: self.fail('屏幕版 CP/M 启动超时')
        for _ in range(100000): machine.step()
        self.assertTrue(vdp.registers[1] & 0x40)
        self.assertIn(b'a>', bytes(vdp.vram[:960]))
        for key in ('d', 'i', 'r', 'Return'):
            keyboard.key_event(key, True)
            for _ in range(30000): machine.step()
            keyboard.key_event(key, False)
            for _ in range(30000): machine.step()
        for _ in range(700000):
            machine.step()
            if b'MBASIC   COM' in serial.output and bytes(serial.output).endswith(b'a>'): break
        else: self.fail(f'DIR 命令未完成: {bytes(serial.output)[-300:]!r}')
        for _ in range(10000): machine.step()
        self.assertIn(b'MBASIC', bytes(vdp.vram[:960]))

if __name__ == '__main__': unittest.main()
