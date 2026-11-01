import sys
import tkinter as tk
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from components.extends.mc6850 import MC6850
from components.extends.tms9918a import TMS9918A
from components.extends.vt82c42 import VT82C42
from platform_core import Machine


class RunningWindowRefreshTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.machine = Machine({'memory': [{'name': 'ROM', 'type': 'rom',
                                            'start': 0, 'size': 65536}]})
        # Poll the ACIA and echo each received character through the real CPU.
        self.machine.memory[0].load(bytes.fromhex('DB 18 E6 01 28 FA DB 19 D3 19 18 F4'))
        self.serial = MC6850(0x18)
        self.video = TMS9918A(0x30)
        self.keyboard = VT82C42(0x20)
        self.machine.attach_decoded_io('串口', self.serial, 0x18, 0xff, 2)
        self.machine.attach_decoded_io('显卡', self.video, 0x30, 0xff, 2)
        self.machine.attach_decoded_io('键盘', self.keyboard, 0x20, 0xff, 2)
        self.machine.bind_keyboard(self.keyboard, self.video)
        self.machine.auto_open_windows = ['串口', '显卡']
        self.app = App(self.root, loaded=(self.machine, 1_000_000))
        self.root.update()

    def tearDown(self):
        if self.root.winfo_exists():
            for identifier in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
                self.root.tk.call('after', 'cancel', identifier)
            self.app.close()

    def test_windows_repaint_and_accept_input_while_machine_runs(self):
        terminal = self.app.component_windows[id(self.serial)]
        text = next(child for child in terminal.winfo_children() if isinstance(child, tk.Text))
        screen = self.app.component_windows[id(self.video)]
        image_label = next(child for child in screen.winfo_children() if hasattr(child, 'image'))
        idle_completed = []

        def type_terminal(key):
            text.focus_force()
            text.event_generate('<KeyPress>', keysym=key)
            self.root.after_idle(lambda: idle_completed.append(True))

        def update_video_and_type():
            # Backdrop color is visible even with the video display disabled.
            self.video.write_port(0x31, 2)
            self.video.write_port(0x31, 0x87)
            screen.focus_force()
            screen.event_generate('<KeyPress>', keysym='b')
            screen.event_generate('<KeyRelease>', keysym='b')

        self.app.start()
        self.root.after(80, lambda: type_terminal('a'))
        self.root.after(160, update_video_and_type)
        self.root.after(350, lambda: type_terminal('c'))
        self.root.after(700, self.root.quit)
        self.root.mainloop()

        self.assertEqual(len(idle_completed), 2, 'Tk idle tasks must continue running during emulation')
        self.assertGreater(self.machine.cycles, 0)
        self.assertIn('ac', text.get('1.0', 'end-1c'))
        self.assertEqual(list(self.keyboard.output), [0x30, 0xb0])
        self.assertEqual(image_label.image.get(0, 0), self.video.palette[2])


if __name__ == '__main__':
    unittest.main()
