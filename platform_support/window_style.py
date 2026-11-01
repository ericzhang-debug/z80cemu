"""Native title-bar controls for Tk child windows."""
import sys
import tkinter as tk

def remove_minimize_maximize(window):
    """Hide both caption buttons on Windows without changing resize capability."""
    if sys.platform != 'win32' or not window.winfo_exists(): return
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    get_style = user32.GetWindowLongPtrW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    set_style = user32.SetWindowLongPtrW
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    set_style.restype = ctypes.c_ssize_t
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL
    handle = user32.GetParent(window.winfo_id()) or window.winfo_id()
    style = get_style(handle, -16)  # GWL_STYLE on the outer Tk wrapper.
    desired = style & ~(0x00020000 | 0x00010000)  # WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    if desired != style:
        set_style(handle, -16, desired)
        user32.SetWindowPos(handle, None, 0, 0, 0, 0, 0x0037)  # frame changed, no move/size/activation

def install_child_window_policy(root):
    """Apply to every mapped Tk Toplevel, including component-owned dialogs."""
    if getattr(root, '_child_window_policy_installed', False): return
    root._child_window_policy_installed = True
    def on_map(event):
        window = event.widget
        if isinstance(window, tk.Toplevel):
            window.after_idle(lambda: remove_minimize_maximize(window) if window.winfo_exists() else None)
    root.bind_all('<Map>', on_map, add='+')
