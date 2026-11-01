"""MSX international keyboard switch matrix; connect to an 8255 separately."""
from platform_support.keyboard import physical_keysym

ROWS = (
    ('0','1','2','3','4','5','6','7'),
    ('8','9','minus','equal','backslash','bracketleft','bracketright','semicolon'),
    ('apostrophe','grave','comma','period','slash','underscore','a','b'),
    tuple('cdefghij'), tuple('klmnopqr'), tuple('stuvwxyz'),
    ('shift_l','control_l','alt_l','caps_lock','alt_r','f1','f2','f3'),
    ('f4','f5','escape','tab','pause','backspace','end','return'),
    ('space','home','insert','delete','left','up','down','right'),
)
KEYS = {key: (row, bit) for row, keys in enumerate(ROWS) for bit, key in enumerate(keys)}
KEYS.update({'shift_r': KEYS['shift_l'], 'control_r': KEYS['control_l'], 'enter': KEYS['return']})

class MSXKeyboard:
    pins = {**{f'ROW{i}': 'input' for i in range(4)}, **{f'COL{i}': 'output' for i in range(8)}}
    def __init__(self): self.pressed = set()
    def reset(self): self.pressed.clear()
    def key_event(self, key, pressed):
        key = physical_keysym(key)
        if key in KEYS:
            if pressed: self.pressed.add(key)
            else: self.pressed.discard(key)
    def read_row(self, row):
        value = 0xff
        for key in self.pressed:
            r, bit = KEYS[key]
            if r == row: value &= ~(1 << bit)
        return value
