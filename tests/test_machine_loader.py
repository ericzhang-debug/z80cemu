import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machine_loader import load_machine

ROOT = Path(__file__).resolve().parents[1]

class MachineLoaderTests(unittest.TestCase):
    def test_builtin_assemblies(self):
        generic, hz = load_machine(ROOT / 'machines/generic.py')
        self.assertEqual(hz, 1_000_000)
        self.assertEqual(generic.ports[0x10].name, 'Z80 CTC')
        board, hz = load_machine(ROOT / 'machines/z80v2.py')
        self.assertEqual(hz, 4_000_000)
        self.assertEqual(board.ports[0x3e].name, 'MC68B50 串口')
        self.assertEqual(board.ports[0xbe].name, 'TMS9918A 显卡')

    def test_external_python_assembly_selects_ports(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'custom.py'
            script.write_text(textwrap.dedent('''
                from platform_core import Machine
                from components.extends.z80_ctc import Z80CTC
                def build():
                    m = Machine({'memory': [{'name':'ram','type':'ram','start':0,'size':65536}]})
                    timer = Z80CTC(0x40)
                    timer.core.connect(0, 1)
                    m.attach_decoded_io('timer', timer, 0x40, 0xff, 4)
                    return m, 2000000
            '''), encoding='utf-8')
            board, hz = load_machine(script)
            self.assertEqual(hz, 2_000_000)
            self.assertIs(board.ports[0x40], board.ports[0xff40])
            self.assertNotIn(0x10, board.ports)
            self.assertEqual(board.ports[0x40].core.links, {0: {1}})

    def test_invalid_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'bad.py'
            for content in ('x=1', 'def build(): return None', 'def build(): return object(), 0'):
                script.write_text(content, encoding='utf-8')
                with self.subTest(content=content), self.assertRaises(ValueError): load_machine(script)

    def test_empty_z80v2_cf_slot(self):
        from boards.z80v2 import Z80V2
        board = Z80V2(cf_image=None)
        self.assertIsNone(board.ports[0xf0].image)
        self.assertEqual(board.io_read(0xf7), 0xff)

    def test_user_wired_ctc_drives_pio_strobe(self):
        board, _ = load_machine(ROOT / 'machines/wired_example.py')
        pio = board.ports[0x14]
        pio.ports[0].set_inputs(0x5a)
        board.io_write(0x10, 0x05)  # timer, constant follows
        board.io_write(0x10, 1)
        board.ports[0x10].tick(20)
        self.assertEqual(board.io_read(0x14), 0x5a)
