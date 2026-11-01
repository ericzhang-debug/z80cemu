"""Host-visible subset of VIA VT82C42 and a PS/2 keyboard.

References: VIA VT82C42 preliminary data sheet and the Z80-V2 kbc.asm.
This models bytes, not PS/2 clock/data electrical timing. Unsupported
controller commands are recorded for diagnostics, not silently interpreted.
"""
from collections import deque
from platform_support.keyboard import physical_keysym

# Scan-set 1 values for the keys used by the original firmware.
SET1 = {
    **dict(zip('1234567890', range(0x02, 0x0c))),
    **dict(zip('qwertyuiop', range(0x10, 0x1a))),
    **dict(zip('asdfghjkl', range(0x1e, 0x27))),
    **dict(zip('zxcvbnm', range(0x2c, 0x33))),
    'escape': 0x01, 'minus': 0x0c, 'equal': 0x0d, 'backspace': 0x0e,
    'tab': 0x0f, 'bracketleft': 0x1a, 'bracketright': 0x1b,
    'return': 0x1c, 'control_l': 0x1d, 'semicolon': 0x27, 'apostrophe': 0x28,
    'grave': 0x29, 'shift_l': 0x2a, 'backslash': 0x2b, 'comma': 0x33,
    'period': 0x34, 'slash': 0x35, 'shift_r': 0x36, 'alt_l': 0x38,
    'space': 0x39, 'caps_lock': 0x3a, 'num_lock': 0x45, 'scroll_lock': 0x46,
    **{f'f{i}': 0x3a + i for i in range(1, 11)}, 'f11': 0x57, 'f12': 0x58,
    'up': 0x48, 'down': 0x50, 'left': 0x4b, 'right': 0x4d,
    'home': 0x47, 'end': 0x4f, 'prior': 0x49, 'next': 0x51,
    'insert': 0x52, 'delete': 0x53,
}
EXTENDED = {'up', 'down', 'left', 'right', 'home', 'end', 'prior', 'next', 'insert', 'delete'}
SET2 = dict(zip('abcdefghijklmnopqrstuvwxyz',
                (0x1c, 0x32, 0x21, 0x23, 0x24, 0x2b, 0x34, 0x33, 0x43,
                 0x3b, 0x42, 0x4b, 0x3a, 0x31, 0x44, 0x4d, 0x15, 0x2d,
                 0x1b, 0x2c, 0x3c, 0x2a, 0x1d, 0x22, 0x35, 0x1a)))
SET2.update(dict(zip('1234567890', (0x16,0x1e,0x26,0x25,0x2e,0x36,0x3d,0x3e,0x46,0x45))))
SET2.update({'escape':0x76, 'minus':0x4e, 'equal':0x55, 'backspace':0x66,
             'tab':0x0d, 'bracketleft':0x54, 'bracketright':0x5b, 'return':0x5a,
             'control_l':0x14, 'semicolon':0x4c, 'apostrophe':0x52, 'grave':0x0e,
             'shift_l':0x12, 'backslash':0x5d, 'comma':0x41, 'period':0x49,
             'slash':0x4a, 'shift_r':0x59, 'alt_l':0x11, 'space':0x29,
             'caps_lock':0x58, 'num_lock':0x77, 'scroll_lock':0x7e,
             'up':0x75, 'down':0x72, 'left':0x6b, 'right':0x74, 'home':0x6c,
             'end':0x69, 'prior':0x7d, 'next':0x7a, 'insert':0x70, 'delete':0x71,
             **{f'f{i}':value for i, value in enumerate((5,6,4,12,3,11,0x83,10,1,9,0x78,7), 1)}})

class VT82C42:
    batch_io_safe = True
    name = 'VT82C42 PS/2 键盘'
    pins = {**{f'D{i}': 'bidirectional' for i in range(8)},
            **{p: 'input' for p in ('A0', '/CS', '/RD', '/WR', 'RESET')},
            **{p: 'bidirectional' for p in ('KBCLK', 'KBDATA', 'MSCLK', 'MSDATA')},
            'P24': 'output', 'P25': 'output'}

    def __init__(self, base=0x2e):
        self.base = base
        self.reset()

    def reset(self):
        self.command_byte = 0x40
        self.output_port = 0x03
        self.last_was_command = False
        self.expect = None
        self.output = deque()
        self.key_enabled = True
        self.scanning = True
        self.keyboard_expect = None
        self.leds = 0
        self.typematic = 0x2b
        self.unsupported_commands = []

    def status(self):
        return ((1 if self.output else 0) | (4 if self.command_byte & 4 else 0)
                | (8 if self.last_was_command else 0) | 0x10)

    def irq_active(self):
        return bool(self.output and self.command_byte & 1)

    def batch_irq_deadline(self):
        # Host input and controller reads happen between batches or at I/O boundaries.
        return None

    def read_port(self, address):
        if (address - self.base) & 1: return self.status()
        return self.output.popleft() if self.output else 0xff

    def write_port(self, address, value):
        value &= 0xff
        self.last_was_command = bool((address - self.base) & 1)
        if self.last_was_command:
            self._command(value)
        elif self.expect is not None:
            command, self.expect = self.expect, None
            if command == 0x60:
                self.command_byte = value
                self.key_enabled = not bool(value & 0x10)
            elif command == 0xd1: self.output_port = value
            elif command in (0xd2, 0xd3): self.output.append(value)
            elif command == 0xd4: self.unsupported_commands.append(command)
        else:
            self._keyboard_command(value)

    def _command(self, value):
        if value == 0x20: self.output.append(self.command_byte)
        elif value in (0x60, 0xd1, 0xd2, 0xd3, 0xd4): self.expect = value
        elif value == 0xaa:
            self.command_byte |= 4
            self.output.append(0x55)
        elif value in (0xa9, 0xab): self.output.append(0)
        elif value == 0xad: self.command_byte |= 0x10; self.key_enabled = False
        elif value == 0xae: self.command_byte &= ~0x10; self.key_enabled = True
        elif value == 0xa7: self.command_byte |= 0x20
        elif value == 0xa8: self.command_byte &= ~0x20
        elif value == 0xd0: self.output.append(self.output_port)
        else: self.unsupported_commands.append(value)

    def _keyboard_command(self, value):
        if self.keyboard_expect:
            if self.keyboard_expect == 0xed: self.leds = value & 7
            elif self.keyboard_expect == 0xf3: self.typematic = value
            elif self.keyboard_expect == 0xf0:
                # Only set 2 device scan codes and translated set 1 are modeled.
                if value == 0: self.output.extend((0xfa, 2)); self.keyboard_expect = None; return
                if value != 2: self.output.append(0xfe); return
            self.keyboard_expect = None
            self.output.append(0xfa)
        elif value in (0xed, 0xf0, 0xf3):
            self.keyboard_expect = value; self.output.append(0xfa)
        elif value == 0xf4: self.scanning = True; self.output.append(0xfa)
        elif value in (0xf5, 0xf6): self.scanning = value == 0xf6; self.output.append(0xfa)
        elif value == 0xff: self.scanning = True; self.output.extend((0xfa, 0xaa))
        elif value == 0xf2: self.output.extend((0xfa, 0xab, 0x83))
        elif value == 0xee: self.output.append(0xee)
        else: self.output.append(0xfe)

    def key_event(self, key, pressed):
        """Queue translated set-1 or native set-2 make/break codes from a Tk keysym."""
        key = physical_keysym(key)
        if not self.key_enabled or not self.scanning: return False
        translated = bool(self.command_byte & 0x40)
        code = (SET1 if translated else SET2).get(key)
        if code is None: return False
        if key in EXTENDED: self.output.append(0xe0)
        if not pressed and not translated: self.output.append(0xf0)
        self.output.append(code | 0x80 if not pressed and translated else code)
        return True
