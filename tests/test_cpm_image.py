import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from firmware.cpm_screen.cpm_image import create_cf_image

class ImageTests(unittest.TestCase):
    def test_padding_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory); source = p/'source'; target = p/'target'
            source.write_bytes(bytes([1])*128 + bytes([2])*128)
            create_cf_image(source, target, sectors=3)
            data = target.read_bytes()
            self.assertEqual(len(data), 1536)
            self.assertEqual(data[:128], bytes([1])*128)
            self.assertEqual(data[128:512], bytes(384))
            self.assertEqual(data[512:640], bytes([2])*128)
            with self.assertRaises(FileExistsError): create_cf_image(source, target, 3)
