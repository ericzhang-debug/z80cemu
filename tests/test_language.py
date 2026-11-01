import json
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from platform_core import Machine
from platform_support import i18n


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'settings.json'
        self.path_patch = patch('platform_support.i18n.settings_path', return_value=self.path)
        self.path_patch.start(); self.addCleanup(self.path_patch.stop)
        self.root = tk.Tk(); self.root.withdraw()
        self.app = None

    def tearDown(self):
        if self.root.winfo_exists():
            self.root.update_idletasks()
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            if self.app: self.app.close()
            else: self.root.destroy()

    def make_app(self):
        machine = Machine({'memory': [{'name': 'RAM', 'type': 'ram', 'start': 0, 'size': 65536}]})
        machine.auto_open_windows = []
        self.app = App(self.root, loaded=(machine, 1000000))
        return self.app

    def test_switch_updates_open_platform_windows_and_persists(self):
        app = self.make_app()
        cpu = app.show_component(app.machine.cpu)
        memory = app.show_component(app.machine.memory[0])
        ports = app.io_window()
        self.root.update()
        menu = self.root.nametowidget(app.menu.entrycget('设置语言', 'menu'))
        menu.invoke('English')
        self.assertEqual(app.language, 'en')
        self.assertEqual(app.run_button.cget('text'), 'Start')
        self.assertEqual(app.status.cget('text'), 'Paused')
        self.assertEqual(cpu.title(), 'Z80 CPU registers')
        self.assertEqual(memory.title(), 'Memory monitor')
        self.assertEqual(ports.title(), 'I/O port monitor')
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['language'], 'en')
        self.assertEqual(i18n.load_language(), 'en')
        app.set_language('zh')
        self.assertEqual(memory.title(), '内存监视器')
        self.assertEqual(app.run_button.cget('text'), '开始')

    def test_new_app_loads_saved_language(self):
        self.path.write_text('{"language": "en"}', encoding='utf-8')
        app = self.make_app()
        self.assertEqual(app.language, 'en')
        self.assertEqual(app.menu.entrycget('Language', 'label'), 'Language')
        self.assertEqual(app.run_button.cget('text'), 'Start')

    def test_switching_language_does_not_clip_tiled_memory_controls(self):
        self.path.write_text('{"language": "en"}', encoding='utf-8')
        app = self.make_app()
        memory = app.show_component(app.machine.memory[0])
        self.root.update()
        app.set_language('zh')
        self.root.update_idletasks()
        toolbar = memory.winfo_children()[0]
        rom_check = toolbar.winfo_children()[-1]
        self.assertGreaterEqual(memory.winfo_width(), memory.winfo_reqwidth())
        self.assertGreaterEqual(rom_check.winfo_width(), rom_check.winfo_reqwidth())

    def test_switching_machine_keeps_language(self):
        app = self.make_app()
        app.set_language('en')
        machine = Machine({'memory': []})
        machine.auto_open_windows = []
        created = []
        def new_app(*args):
            created.append(App(*args))
            return created[-1]
        with patch('app.filedialog.askopenfilename', return_value='other.py'), \
             patch('app.load_machine', return_value=(machine, 2000000)), \
             patch('app.App', side_effect=new_app):
            app.open_machine()
        self.assertFalse(app.active)
        self.assertEqual(len(created), 1)
        self.app = created[0]
        self.assertEqual(self.app.language, 'en')
        self.assertEqual(self.app.run_button.cget('text'), 'Start')

    def test_bad_settings_and_write_failure(self):
        self.path.write_text('{invalid', encoding='utf-8')
        self.assertEqual(i18n.load_language(), 'zh')
        app = self.make_app()
        with patch('platform_support.i18n.save_language', side_effect=PermissionError('denied')):
            with patch('app.messagebox.showerror') as showerror:
                app.set_language('en')
        self.assertEqual(app.language, 'zh')
        self.assertEqual(app._language_var.get(), 'zh')
        showerror.assert_called_once()
        self.assertIn('denied', showerror.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
