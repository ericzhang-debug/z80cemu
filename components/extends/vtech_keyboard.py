"""VTech Laser/VZ eight-row, six-column active-low keyboard matrix."""

class VTechKeyboard:
    pins = {'A0-A7': 'input', 'D0-D5': 'output'}
    # Keys ordered from bit 0 to bit 5 for each active-low address row.
    rows = (('t','w',None,'e','q','r'), ('g','s','control','d','a','f'),
            ('b','x','shift','c','z','v'), ('5','2',None,'3','1','4'),
            ('n','period',None,'comma','space','m'), ('6','9','minus','8','0','7'),
            ('y','o','return','i','p','u'), ('h','l','colon','k','semicolon','j'))
    aliases = {'Shift_L':'shift', 'Shift_R':'shift', 'Control_L':'control',
               'Control_R':'control', 'Return':'return', 'KP_Enter':'return',
               'Escape':'minus'}
    arrows = {'Left': 'm', 'Right': 'comma', 'Up': 'period', 'Down': 'space',
              'BackSpace': 'm', 'Delete': 'm'}
    # Laser/VZ BASIC places several symbols on different keys from a PC.
    # Values specify the emulated key and whether its shift switch is needed.
    symbols = {
        'exclam': ('1', True), 'at': ('0', True), 'numbersign': ('3', True),
        'dollar': ('4', True), 'percent': ('5', True), 'ampersand': ('6', True),
        'apostrophe': ('7', True), 'parenleft': ('8', True), 'parenright': ('9', True),
        'asterisk': ('semicolon', True), 'plus': ('colon', True),
        'equal': ('minus', True), 'quotedbl': ('2', True), 'colon': ('colon', False),
        'less': ('comma', True), 'greater': ('period', True),
    }

    def __init__(self): self.reset()
    def reset(self): self.pressed = set(); self._held = {}; self._shift_modes = {}
    def key_event(self, keysym, pressed):
        if pressed:
            if keysym in self.arrows: self._held[keysym] = ('control', self.arrows[keysym])
            elif keysym.lower() in self.symbols:
                key, shift = self.symbols[keysym.lower()]
                self._held[keysym] = (key,)
                self._shift_modes[keysym] = shift
            else: self._held[keysym] = (self.aliases.get(keysym, keysym.lower()),)
        else:
            self._held.pop(keysym, None)
            self._shift_modes.pop(keysym, None)
        self.pressed = {key for group in self._held.values() for key in group}
        if self._shift_modes:
            if next(reversed(self._shift_modes.values())): self.pressed.add('shift')
            else: self.pressed.discard('shift')
    def read(self, address):
        value = 0x3f
        for row, keys in enumerate(self.rows):
            if not address & (1 << row):
                for bit, key in enumerate(keys):
                    if key and key in self.pressed: value &= ~(1 << bit)
        return value
