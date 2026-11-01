"""Exercise the actual Laser 310 BASIC ROM through its printer I/O ports."""
import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from machines.laser310 import build
from tests.test_laser310 import run_cycles, screen_text


def type_keys(machine, text):
    """Enter characters through the same keyboard matrix used by the GUI."""
    for char in text:
        key = {' ': 'space', '\n': 'Return', '"': 'quotedbl', '-': 'minus'}.get(char, char)
        machine.keyboard.key_event(key, True)
        run_cycles(machine, 220_000)
        machine.keyboard.key_event(key, False)
        run_cycles(machine, 220_000)


class LaserPrinterFirmwareTests(unittest.TestCase):
    def test_firmware_waits_offline_and_gui_shows_resumed_printing(self):
        machine, _ = build()
        printer = machine.printer
        printer.online = False
        root = tk.Tk(); root.withdraw()
        window = printer.open_gui(root, lambda: None)
        try:
            root.update()
            run_cycles(machine, 10_000_000)
            type_keys(machine, 'lprint "a"\n')
            run_cycles(machine, 1_000_000)
            self.assertTrue(printer.read_port(0) & 1)
            self.assertEqual(bytes(printer.output), b'')

            bar, frame = window.winfo_children()
            online = next(child for child in bar.winfo_children() if isinstance(child, ttk.Checkbutton))
            online.invoke()
            self.assertFalse(printer.read_port(0) & 1)
            run_cycles(machine, 1_000_000)
            self.assertEqual(bytes(printer.output), b'A\r\n')
            root.after(200, root.quit); root.mainloop()
            text = next(child for child in frame.winfo_children() if isinstance(child, tk.Text))
            self.assertEqual(text.get('1.0', 'end-1c'), 'A\n')
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            root.destroy()

    def test_lprint_llist_and_copy_from_actual_firmware(self):
        machine, _ = build()
        run_cycles(machine, 10_000_000)
        printer = machine.printer

        type_keys(machine, 'lprint "hello"\n')
        run_cycles(machine, 1_000_000)
        self.assertEqual(bytes(printer.output), b'HELLO\r\n')

        printer.clear_paper()
        type_keys(machine, '10 print 123\n')
        type_keys(machine, 'llist\n')
        run_cycles(machine, 1_000_000)
        self.assertEqual(bytes(printer.output), b'10 PRINT 123\r\n')

        printer.clear_paper()
        type_keys(machine, '20 print 456\n')
        type_keys(machine, 'llist 10-10\n')
        run_cycles(machine, 1_000_000)
        self.assertEqual(bytes(printer.output), b'10 PRINT 123\r\n')

        printer.clear_paper()
        type_keys(machine, 'copy')
        rows = screen_text(machine).splitlines()
        self.assertEqual(len(rows), 16)
        expected = ''.join(row + '\r\n' for row in rows).encode('ascii')
        type_keys(machine, '\n')
        run_cycles(machine, 2_000_000)
        self.assertEqual(bytes(printer.output), expected)


if __name__ == '__main__':
    unittest.main()
