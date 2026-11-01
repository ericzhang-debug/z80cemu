import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from components.extends.vtech_printer import VTechPrinter
from machines.laser310 import build
from app import App


class VTechPrinterTests(unittest.TestCase):
    def test_platform_reset_preserves_printer_paper(self):
        machine, clock = build()
        root = tk.Tk(); root.withdraw()
        app = App(root, loaded=(machine, clock))
        try:
            printer = machine.printer
            self.assertIs(machine.ports[0x1200], printer)
            self.assertIs(machine.ports[0x120d], printer)
            self.assertIs(machine.ports[0x120e], printer)
            self.assertIn(id(printer), app.component_windows)
            for byte in b'paper\r\n': machine.io_write(0x120e, byte)
            app.reset()
            self.assertEqual(bytes(printer.output), b'paper\r\n')
            self.assertEqual(printer.paper_text, 'paper\n')
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            app.close()

    def test_port_protocol_and_busy(self):
        printer = VTechPrinter()
        self.assertEqual(printer.read_port(0x1200) & 1, 0)
        printer.write_port(0x410e, ord('A'))
        printer.write_port(0x410d, ord('A'))
        self.assertEqual(printer.raw, b'A')
        self.assertIs(printer.output, printer.raw)
        self.assertEqual(printer.last_write_port, 0x0d)
        printer.online = False
        self.assertEqual(printer.read_port(0) & 1, 1)
        printer.write_port(0x0e, ord('B'))
        self.assertEqual(printer.raw, b'A')
        printer.online = True
        printer.write_port(0x0e, ord('C'))
        printer.reset()
        self.assertEqual(printer.raw, b'AC')
        self.assertEqual(printer.paper_text, 'AC')

    def test_paper_controls_and_raw_export(self):
        printer = VTechPrinter()
        data = b'AB\bC\rX\nY\fZ\x01'
        for byte in data: printer.write_port(0x0e, byte)
        self.assertEqual(printer.paper_text, 'XC\n Y\fZ')
        self.assertEqual(printer.raw, data)
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / 'paper.bin'
            text = Path(directory) / 'paper.txt'
            printer.save_raw(raw); printer.save_text(text)
            self.assertEqual(raw.read_bytes(), data)
            self.assertEqual(text.read_bytes(), b'XC\n Y\fZ')
        printer.clear_paper()
        self.assertEqual(printer.raw, b'')
        self.assertEqual(printer.paper_text, '')

    def test_window_reopens_with_history_and_refreshes(self):
        root = tk.Tk(); root.withdraw()
        printer = VTechPrinter()
        for value in b'before\r\n': printer.write_port(0x0e, value)
        try:
            window = printer.open_gui(root, lambda: None)
            root.update()
            def descend(widget):
                return [child for child in widget.winfo_children() for child in [child, *descend(child)]]
            text = next(child for child in descend(window) if isinstance(child, tk.Text))
            self.assertEqual(text.get('1.0', 'end-1c'), 'before\n')
            window.destroy()
            for value in b'after': printer.write_port(0x0e, value)
            window = printer.open_gui(root, lambda: None)
            root.update()
            text = next(child for child in descend(window) if isinstance(child, tk.Text))
            self.assertEqual(text.get('1.0', 'end-1c'), 'before\nafter')
            button = next(child for child in descend(window)
                          if isinstance(child, tk.Button) and child.cget('text') == '清空')
            button.invoke()
            root.after(200, root.quit); root.mainloop()
            self.assertEqual(text.get('1.0', 'end-1c'), '')
            self.assertEqual(printer.raw, b'')
        finally:
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')):
                root.tk.call('after', 'cancel', identifier)
            root.update_idletasks(); root.destroy()


if __name__ == '__main__': unittest.main()
