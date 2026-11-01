import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.compact_flash import CompactFlash
from ui.cf_editor import CFImageEditor, create_blank_image

class CFEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.original = self.directory / 'source.img'
        self.original.write_bytes(bytes(range(256)) * 4)
        self.card = CompactFlash(0xf0)
        self.editor = CFImageEditor(self.card)

    def tearDown(self): self.tmp.cleanup()

    def test_empty_mount_eject_and_failed_mount_preserves_old_medium(self):
        self.assertEqual(self.card.read_port(0xf7), 0xff)
        self.editor.mount(self.original)
        self.assertEqual(self.card.sectors, 2)
        invalid = self.directory / 'invalid.img'; invalid.write_bytes(b'x')
        with self.assertRaises(ValueError): self.editor.mount(invalid)
        self.assertEqual(self.card.image, self.original)
        self.editor.eject()
        self.assertIsNone(self.card.image)
        self.assertEqual(self.card.read_port(0xf7), 0xff)

    def test_import_across_sectors_and_export_preserves_source(self):
        original = self.original.read_bytes()
        self.editor.mount(self.original)
        self.editor.import_bytes(510, b'ABCDE')
        self.assertEqual(self.editor.sector(0)[510:], b'AB')
        self.assertEqual(self.editor.sector(1)[:3], b'CDE')
        target = self.directory / 'new.img'
        self.editor.export(target)
        self.assertEqual(target.read_bytes()[510:515], b'ABCDE')
        self.assertEqual(self.original.read_bytes(), original)
        with self.assertRaises((ValueError, FileExistsError)): self.editor.export(self.original)
        with self.assertRaises(FileExistsError): self.editor.export(target)
        self.assertEqual(target.read_bytes()[510:515], b'ABCDE')

    def test_invalid_edit_or_import_has_no_partial_changes(self):
        self.editor.mount(self.original)
        with self.assertRaises(ValueError): self.editor.edit(0, b'bad')
        with self.assertRaises(ValueError): self.editor.import_bytes(1023, b'too long')
        with self.assertRaises(ValueError): self.editor.sector(2)
        self.assertEqual(self.editor.changes, {})

    def test_create_exclusive_and_mount_writable(self):
        target = self.directory / 'blank.img'
        create_blank_image(target, 4)
        self.assertEqual(target.stat().st_size, 2048)
        with self.assertRaises(FileExistsError): create_blank_image(target, 2)
        self.editor.mount(target, readonly=False)
        self.assertFalse(self.card.readonly)
        self.editor.eject()
        self.assertEqual(self.card.sectors, 0)

    def test_export_then_mount_is_visible_through_ata(self):
        self.editor.mount(self.original)
        self.editor.import_bytes(512, b'FIRMWARE')
        target = self.directory / 'firmware.img'
        self.editor.export(target)
        self.editor.mount(target)
        self.card.write_port(0xf2, 1)
        self.card.write_port(0xf3, 1)
        self.card.write_port(0xf6, 0xe0)
        self.card.write_port(0xf7, 0x20)
        self.assertEqual(bytes(self.card.read_port(0xf0) for _ in range(8)), b'FIRMWARE')

if __name__ == '__main__': unittest.main()
