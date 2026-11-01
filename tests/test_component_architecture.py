import ast
import unittest
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ComponentArchitectureTests(unittest.TestCase):
    def test_platform_entry_and_core_do_not_import_expansion_components(self):
        for filename in ('app.py', 'platform_core.py', 'machine_loader.py'):
            path = ROOT / filename
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith('components.extends'), filename)
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith('components.extends') for alias in node.names), filename)

    def test_cli_requires_explicit_machine_before_opening_ui(self):
        import sys
        result = subprocess.run([sys.executable, str(ROOT / 'app.py')], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--machine', result.stderr)
    def test_extension_modules_do_not_import_each_other(self):
        extensions = ROOT / 'components' / 'extends'
        for path in extensions.glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(node.level or (node.module or '').startswith('components.extends'), str(path))
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith('components.extends') for alias in node.names), str(path))

    def test_base_and_named_extensions_present(self):
        for name in ('cpu.py', 'ram.py', 'rom.py'):
            self.assertTrue((ROOT / 'components' / name).is_file())
        for name in ('z80_ctc.py', 'z80_pio.py', 'mc6850.py', 'tms9918a.py', 'vt82c42.py', 'sn76489.py', 'compact_flash.py', 'joypad.py'):
            self.assertTrue((ROOT / 'components' / 'extends' / name).is_file())
