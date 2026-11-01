import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines import z80v2


class Z80V2ConfigLocationTests(unittest.TestCase):
    def test_machine_config_and_relative_images(self):
        path = z80v2.CONFIG_PATH
        self.assertEqual(path.parent, Path(z80v2.__file__).resolve().parent)
        config = json.loads(path.read_text(encoding='utf-8'))
        machine, clock = z80v2.build()
        self.assertEqual(clock, config['clock_hz'])
        if config.get('rom_image'):
            image = (path.parent / config['rom_image']).resolve().read_bytes()
            self.assertEqual(machine.rom.data[:len(image)], image)


if __name__ == '__main__':
    unittest.main()
