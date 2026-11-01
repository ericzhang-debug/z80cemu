"""MC6847 display modes used by the unmodified Laser 310 board.

The caller supplies video RAM and the character generator ROM; no board is
imported here. Timing is frame based, not a scanline/composite simulation.
"""

class MC6847:
    gui_resizable = True
    pins = {'D0-D7': 'input', 'A0-A12': 'output', 'A/G': 'input',
            'CSS': 'input', 'FS': 'output', 'VIDEO': 'output'}
    palette = ((0, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
               (255, 0, 0), (255, 255, 255), (0, 255, 255), (255, 0, 255),
               (255, 128, 0), (0, 64, 0), (96, 48, 0))

    def __init__(self, ram, glyphs):
        if len(ram) < 0x800 or len(glyphs) != 3072:
            raise ValueError('MC6847 需要 2 KiB 显存和 3072 字节字模')
        self.ram, self.glyphs = ram, bytes(glyphs)
        self.reset()

    def reset(self):
        self.mode = 0
        self.visual_revision = getattr(self, 'visual_revision', 0) + 1

    def set_mode(self, value):
        mode = value & 0x18
        if mode != self.mode:
            self.mode = mode
            self.visual_revision += 1

    def changed(self):
        self.visual_revision += 1

    def render(self):
        pixels = bytearray(256 * 192)
        if self.mode & 8:  # GM2:GM0=010: 128x64, four colours.
            colors = (5, 6, 7, 8) if self.mode & 16 else (1, 2, 3, 4)
            for y in range(192):
                for xbyte in range(32):
                    value = self.ram[(y // 3) * 32 + xbyte]
                    for bit in range(4):
                        color = colors[(value >> (6 - bit * 2)) & 3]
                        pos = y * 256 + xbyte * 8 + bit * 2
                        pixels[pos:pos + 2] = bytes((color, color))
            return pixels
        for row in range(16):
            for col in range(32):
                value = self.ram[row * 32 + col]
                foreground = (value >> 4 & 7) + 1 if value & 0x80 else (8 if self.mode & 16 else 1)
                background = 0 if value & 0x80 else (10 if self.mode & 16 else 9)
                glyph = value * 12
                for line in range(12):
                    bits = self.glyphs[glyph + line]
                    pos = (row * 12 + line) * 256 + col * 8
                    # Character ROM rows are stored left-to-right, low bit first.
                    for bit in range(8): pixels[pos + bit] = foreground if bits & (1 << bit) else background
        return pixels

    def open_gui(self, root, pause):
        import tkinter as tk
        from tkinter import ttk
        window = tk.Toplevel(root); window.title(self.name)
        window.geometry('560x430'); window.minsize(270, 230)
        window.tile_preferred = (560, 430)
        label = ttk.Label(window, anchor='center'); label.pack(fill='both', expand=True)
        label.bind('<Button-1>', lambda event: window.focus_set())
        rendered = [None, None]
        tables = [bytes([rgb[c] for rgb in self.palette] + [0] * (256 - len(self.palette))) for c in range(3)]
        def update():
            if not window.winfo_exists(): return
            scale = max(1, min(label.winfo_width() // 256, label.winfo_height() // 192))
            if rendered != [self.visual_revision, scale]:
                indices = bytes(self.render()); rgb = bytearray(len(indices) * 3)
                for channel, table in enumerate(tables): rgb[channel::3] = indices.translate(table)
                label.image = tk.PhotoImage(data=b'P6\n256 192\n255\n' + rgb, format='PPM')
                if scale > 1: label.image = label.image.zoom(scale)
                label.configure(image=label.image)
                rendered[:] = [self.visual_revision, scale]
            window.after(100, update)
        update()
        return window
