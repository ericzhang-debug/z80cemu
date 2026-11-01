"""TMS9918A functional model, 16 KiB VRAM and a frame-based video output.

Register and video rules are from TI's 1982 TMS9918A data manual. This model
does not emulate the DRAM access windows, analog video, or scanline-time writes.
"""

class TMS9918A:
    gui_resizable = True
    def open_gui(self, root, pause):
        from ui.component_views import video_window
        return video_window(root, self, pause)
    batch_tick_safe = True
    batch_io_safe = True
    pins = {'D0-D7': 'bidirectional', 'MODE': 'input', '/CSR': 'input',
            '/CSW': 'input', '/INT': 'output', 'EXTVDP': 'input', 'VIDEO': 'output'}
    width = 256
    height = 192
    palette = (
        (0, 0, 0), (0, 0, 0), (33, 200, 66), (94, 220, 120),
        (84, 85, 237), (125, 118, 252), (212, 82, 77), (66, 235, 245),
        (252, 85, 84), (255, 121, 120), (212, 193, 84), (230, 206, 128),
        (33, 176, 59), (201, 91, 186), (204, 204, 204), (255, 255, 255),
    )

    def __init__(self, base=0xbe, cpu_hz=4_000_000, frame_rate=60):
        if cpu_hz <= 0 or frame_rate <= 0: raise ValueError('invalid video clock')
        self.base, self.cpu_hz, self.frame_rate = base, cpu_hz, frame_rate
        self.vram = bytearray(0x4000)
        self.reset()

    def reset(self):
        self.visual_revision = getattr(self, 'visual_revision', 0) + 1
        self.registers = bytearray(8)
        self.address = 0
        self.read_buffer = 0
        self.control_latch = None
        self.status = 0x1f
        self.frame_phase = 0
        self.frame_number = 0

    def irq_active(self):
        return bool(self.status & 0x80 and self.registers[1] & 0x20)

    def batch_irq_deadline(self):
        if not self.registers[1] & 0x20 or self.status & 0x80: return None
        return max(1, (self.cpu_hz - self.frame_phase + self.frame_rate - 1) // self.frame_rate)

    def read_port(self, address):
        if (address - self.base) & 1:
            result = self.status
            self.status = 0x1f
            self.control_latch = None
            return result
        self.control_latch = None
        result = self.read_buffer
        self.read_buffer = self.vram[self.address]
        self.address = (self.address + 1) & 0x3fff
        return result

    def write_port(self, address, value):
        value &= 255
        if not (address - self.base) & 1:
            self.control_latch = None
            if self.vram[self.address] != value: self.visual_revision += 1
            self.vram[self.address] = value
            self.read_buffer = value
            self.address = (self.address + 1) & 0x3fff
            return
        if self.control_latch is None:
            self.control_latch = value
            return
        first = self.control_latch
        self.control_latch = None
        if value & 0x80:
            if self.registers[value & 7] != first: self.visual_revision += 1
            self.registers[value & 7] = first
        else:
            self.address = ((value & 0x3f) << 8 | first) & 0x3fff
            if not value & 0x40:
                self.read_buffer = self.vram[self.address]
                self.address = (self.address + 1) & 0x3fff

    def tick(self, cycles):
        # Integer accumulator avoids drifting when CPU frequency is not divisible by 60.
        self.frame_phase += cycles * self.frame_rate
        while self.frame_phase >= self.cpu_hz:
            self.frame_phase -= self.cpu_hz
            self.frame_number += 1
            if self.registers[1] & 0x40 and not self.registers[1] & 0x10:
                self._sprites(None, True)
            self.status |= 0x80

    def render(self):
        """Return 256x192 color indices, row-major, for a display consumer."""
        r = self.registers
        back = r[7] & 15
        screen = bytearray([back] * (self.width * self.height))
        if not r[1] & 0x40: return screen
        text = bool(r[1] & 0x10)
        multi = bool(r[1] & 0x08)
        graphic2 = bool(r[0] & 0x02)
        # The three legal mode flags are mutually exclusive.
        if int(text) + int(multi) + int(graphic2) > 1: return screen
        name_base = (r[2] & 15) << 10
        pattern_base = (r[4] & 7) << 11
        color_base = r[3] << 6
        cols = 40 if text else 32
        for y in range(192):
            row, line = divmod(y, 8)
            for col in range(cols):
                name = self.vram[(name_base + row * cols + col) & 0x3fff]
                if multi:
                    color = self.vram[(pattern_base + name * 8 + (row & 3) * 2 + line // 4) & 0x3fff]
                    pattern = 0xf0
                elif graphic2:
                    logical = ((row & 0x18) << 8) | (name << 3) | line
                    pattern_mask = ((r[4] & 3) << 11) | 0x7ff
                    color_mask = ((r[3] & 0x7f) << 6) | 0x3f
                    pattern = self.vram[(((r[4] & 4) << 11) | (logical & pattern_mask)) & 0x3fff]
                    color = self.vram[(((r[3] & 0x80) << 6) | (logical & color_mask)) & 0x3fff]
                else:
                    pattern = self.vram[(pattern_base + name * 8 + line) & 0x3fff]
                    color = r[7] if text else self.vram[(color_base + (name >> 3)) & 0x3fff]
                fg, bg = color >> 4 or back, color & 15 or back
                left = (8 + col * 6) if text else col * 8
                for bit in range(6 if text else 8):
                    screen[y * 256 + left + bit] = fg if pattern & (0x80 >> bit) else bg
        if not text: self._sprites(screen, False)
        return screen

    def _sprites(self, screen, update_status):
        r, mem = self.registers, self.vram
        attr = (r[5] & 0x7f) << 7
        patterns = (r[6] & 7) << 11
        size = 16 if r[1] & 2 else 8
        mag = 2 if r[1] & 1 else 1
        per_line = [0] * 192
        occupied = bytearray(256 * 192)
        drawn = bytearray(256 * 192) if screen is not None else None
        overflow = None
        collision = False
        for sprite in range(32):
            a = (attr + sprite * 4) & 0x3fff
            yraw, x, number, tag = (mem[(a + k) & 0x3fff] for k in range(4))
            if yraw == 0xd0: break
            top = yraw + 1
            if top >= 225: top -= 256
            x -= 32 if tag & 0x80 else 0
            if size == 16: number &= 0xfc
            for sy in range(size * mag):
                y = top + sy
                if not 0 <= y < 192: continue
                per_line[y] += 1
                if per_line[y] == 5 and overflow is None: overflow = sprite
                if per_line[y] > 4: continue
                row = sy // mag
                for sx in range(size * mag):
                    px = sx // mag
                    target = x + sx
                    if not 0 <= target < 256: continue
                    # 16x16 sprite pattern is stored column-major as four 8x8 patterns.
                    tile = number + (2 if px >= 8 else 0) + (1 if row >= 8 else 0)
                    bits = mem[(patterns + tile * 8 + (row & 7)) & 0x3fff]
                    if not bits & (0x80 >> (px & 7)): continue
                    index = y * 256 + target
                    if occupied[index]: collision = True
                    if screen is not None and tag & 15 and not drawn[index]:
                        screen[index] = tag & 15
                        drawn[index] = 1
                    occupied[index] = 1
        if update_status:
            if collision: self.status |= 0x20
            if overflow is not None and not self.status & 0x40:
                self.status = (self.status & 0xe0) | 0x40 | overflow
