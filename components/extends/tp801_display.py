"""TP801 six-digit multiplexed, active-low seven-segment display."""
import tkinter as tk

class TP801Display:
    name = 'TP801 六位数码管'
    pins = {**{f'/SEG{i}': 'input' for i in range(7)},
            **{f'DIGIT{i}': 'input' for i in range(6)}}

    def __init__(self): self.reset()

    def reset(self):
        self.segments = 0xff
        self.digits = 0
        self.exposure = [{} for _ in range(6)]
        self.exposure_cycles = 0
        self.display = [0x7f] * 6

    def set_segments(self, value): self.segments = value & 0xff
    def set_digits(self, value): self.digits = value & 0xff

    def tick(self, cycles):
        if cycles < 0: raise ValueError('cycles must not be negative')
        self.exposure_cycles += cycles
        if self.digits and self.segments & 0x7f != 0x7f:
            for index, counts in enumerate(self.exposure):
                if self.digits & (1 << (5 - index)):
                    counts[self.segments] = counts.get(self.segments, 0) + cycles

    def sample(self):
        threshold = max(1, self.exposure_cycles // 200)
        result = []
        for counts in self.exposure:
            pattern = 0x7f
            for value, duration in counts.items():
                if duration >= threshold: pattern &= value
            result.append(pattern)
        self.exposure = [{} for _ in range(6)]
        self.exposure_cycles = 0
        self.display = result
        return result[:]

    def open_gui(self, root, pause):
        window = tk.Toplevel(root); window.title(self.name)
        canvas = tk.Canvas(window, width=282, height=58, bg='#171717', highlightthickness=0)
        canvas.pack(padx=3, pady=3)
        # Segment bit order: a, b, c, d, e, f, g. Low level lights a segment.
        shapes = ((7, 2, 31, 5), (32, 6, 35, 23), (32, 28, 35, 45),
                  (7, 46, 31, 49), (3, 28, 6, 45), (3, 6, 6, 23), (7, 24, 31, 27))
        segments = []
        for digit in range(6):
            x = 5 + digit * 45
            segments.append([canvas.create_rectangle(x+a, b, x+c, d, fill='#441111', outline='')
                             for a,b,c,d in shapes])
        def update():
            if not window.winfo_exists(): return
            for items, pattern in zip(segments, self.sample()):
                for bit, item in enumerate(items):
                    canvas.itemconfigure(item, fill='#ff402b' if not pattern & (1 << bit) else '#441111')
            window.after(100, update)
        update()
        return window
