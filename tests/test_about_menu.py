import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import APP_VERSION, App
from machines.generic import build


class AboutMenuTests(unittest.TestCase):
    def test_menu_shows_version_and_copyright_notices(self):
        machine, clock = build()
        machine.auto_open_windows = []
        root = tk.Tk()
        root.withdraw()
        with patch('app.i18n.load_language', return_value='zh'):
            app = App(root, loaded=(machine, clock))
        try:
            menu = root.nametowidget(root['menu'])
            with patch('app.messagebox.showinfo') as showinfo:
                menu.invoke('关于')
            title, content = showinfo.call_args.args
            self.assertIn('关于', title)
            for expected in (APP_VERSION, 'Eric'):
                self.assertIn(expected, content)
            self.assertNotIn('Bitrowz', content)
            self.assertIs(showinfo.call_args.kwargs['parent'], root)
            with patch('app.messagebox.showinfo') as showinfo:
                menu.invoke('第三方程序使用')
            content = showinfo.call_args.args[1]
            for expected in ('Manuel Sainz de Baranda y Goñi', 'LGPL v3', 'Bitrowz', 'GPL v3', '北京工业大学'):
                self.assertIn(expected, content)
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            app.close()


if __name__ == '__main__':
    unittest.main()
