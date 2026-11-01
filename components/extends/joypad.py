"""Z80-V2 SG-1000 compatible pair of active-low digital controllers.

Port selection is supplied by the board decoder.  The two six-button pads
are packed across the two input bytes as on the SG-1000 controller interface.
"""

class Joypads:
    def open_gui(self, root, pause):
        from ui.component_views import joypad_window
        return joypad_window(root, self, pause)
    batch_io_safe = True
    name = 'SG-1000 游戏控制器'
    buttons = ('up', 'down', 'left', 'right', 'button1', 'button2')
    pins = {**{f'D{i}': 'output' for i in range(8)},
            **{f'P{p}_{b}': 'input' for p in (1, 2) for b in ('up', 'down', 'left', 'right', 'button1', 'button2')},
            '/CS': 'input', '/RD1': 'input', '/RD2': 'input'}

    def __init__(self):
        self.reset()

    def reset(self):
        self.pressed = [set(), set()]
        self.console = False

    def set_button(self, player, button, pressed):
        if player not in (1, 2) or button not in self.buttons:
            raise ValueError('invalid controller or button')
        buttons = self.pressed[player - 1]
        if pressed: buttons.add(button)
        else: buttons.discard(button)

    def read_port(self, address):
        def bits(player):
            return sum((0 if button in self.pressed[player] else 1) << i
                       for i, button in enumerate(self.buttons))
        p1, p2 = bits(0), bits(1)
        if address & 1:
            return 0xe0 | (0 if self.console else 0x10) | ((p2 >> 2) & 15)
        return p1 | ((p2 & 3) << 6)

    def write_port(self, address, value):
        pass  # The GAL enables the interface for reads only.
