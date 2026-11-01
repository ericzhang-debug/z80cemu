import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends import tp801_cassette as cassette

class IdleRoot:
    def __init__(self): self.pending = []
    def after_idle(self, callback): self.pending.append(callback)
    def fire(self): self.pending.pop(0)()

class CassetteComponentTests(unittest.TestCase):
    def setUp(self):
        self.memory = bytearray(65536)
        self.pauses = []
        self.root = IdleRoot()
        def write_batch(image):
            if any(address < 0x2000 for address in image): raise ValueError('ROM')
            for address, value in image.items(): self.memory[address] = value
        self.device = cassette.TP801Cassette(self.memory.__getitem__, write_batch, lambda: (0x2000, 0x2003))
        self.device.bind_ui(self.root, lambda: self.pauses.append(True))

    def test_read_request_automatically_opens_dialog_and_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.wav'
            original = bytes.fromhex('12 34 ab cd')
            contents = cassette.records(lambda addr: original[addr - 0x2000], 0x2000, 0x2003)
            cassette.write_wav(path, contents, leader_seconds=1, trailer_seconds=1)
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)) as choose:
                self.device.request_load(); self.assertEqual(len(self.pauses), 1)
                choose.assert_not_called(); self.root.fire(); choose.assert_called_once()
            self.assertEqual(self.memory[0x2000:0x2004], original)

    def test_send_request_automatically_opens_dialog_and_saves(self):
        self.memory[0x2000:0x2004] = bytes.fromhex('10 20 30 40')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / 'out.wav'
            real = cassette.write_wav
            with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)) as choose, \
                 patch.object(cassette, 'write_wav', side_effect=lambda p, text: real(p, text, 1, 1)):
                self.device.request_save(); self.root.fire(); choose.assert_called_once()
            self.assertEqual(cassette.read_wav(path), dict(zip(range(0x2000, 0x2004), [0x10, 0x20, 0x30, 0x40])))
            self.assertEqual(len(self.pauses), 1)

    def test_cancel_does_not_mutate_memory(self):
        with patch('tkinter.filedialog.askopenfilename', return_value=''):
            self.device.request_load(); self.root.fire()
        self.assertEqual(self.memory[0x2000:0x2004], bytes(4))

if __name__ == '__main__': unittest.main()
