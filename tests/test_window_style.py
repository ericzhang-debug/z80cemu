import sys
import tkinter as tk
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_support.window_style import install_child_window_policy

@unittest.skipUnless(sys.platform == 'win32', 'Windows 标题栏样式测试')
class WindowStyleTests(unittest.TestCase):
    def test_child_and_nested_child_have_no_min_max_but_can_resize(self):
        import ctypes
        from ctypes import wintypes
        root = tk.Tk(); root.withdraw(); install_child_window_policy(root)
        window = tk.Toplevel(root); window.resizable(True, True)
        dialog = tk.Toplevel(window); dialog.resizable(True, True)
        try:
            root.update()
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]; user32.GetParent.restype = wintypes.HWND
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            for child in (window, dialog):
                handle = user32.GetParent(child.winfo_id())
                style = user32.GetWindowLongPtrW(handle, -16)
                self.assertEqual(style & 0x30000, 0)
                self.assertTrue(style & 0x80000)  # system menu, including Close
                self.assertEqual(tuple(map(int, child.resizable())), (1, 1))
        finally:
            root.destroy()
