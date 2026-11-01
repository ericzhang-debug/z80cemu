import sys
import tkinter as tk
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App
from boards.z80v2 import Z80V2

class VideoIntegrationTests(unittest.TestCase):
    def test_cpu_program_updates_video_window(self):
        board = Z80V2(); board.auto_open_windows = []
        # OUT to BFh: set R7 foreground/background, then enable display in R1.
        board.rom.load(bytes.fromhex('3e f4 d3 bf 3e 87 d3 bf 3e 40 d3 bf 3e 81 d3 bf 76'))
        root = tk.Tk(); root.withdraw(); app = App(root, loaded=(board, 4000000))
        try:
            video = board.ports[0xbe]
            window = app.show_component(video)
            for _ in range(8): board.step()
            root.after(160, root.quit); root.mainloop()
            labels = window.winfo_children()
            self.assertEqual(labels[0].cget('text'), '视频输出已启用')
            self.assertEqual(labels[1].image.get(0, 0), video.palette[4])
            self.assertGreater(sum(n for port, n in board.io_counts.items() if port & 0xff == 0xbf), 0)
        finally:
            root.update_idletasks()
            for identifier in root.tk.splitlist(root.tk.call('after', 'info')): root.tk.call('after', 'cancel', identifier)
            app.close()

if __name__ == '__main__': unittest.main()
