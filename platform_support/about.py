"""Platform attribution, separate from machine and expansion implementations."""
from tkinter import messagebox

APP_VERSION = '0.1.0'


def show_about(root, language):
    if language == 'en':
        title = 'About z80cemu'
        text = f'z80cemu {APP_VERSION}\nCopyright © Eric\nhttps://github.com/ericzhang-debug/z80cemu'
    else:
        title = '关于z80cemu'
        text = f'z80cemu {APP_VERSION}\n版权所有 © Eric\nhttps://github.com/ericzhang-debug/z80cemu'
    messagebox.showinfo(title, text, parent=root)


def show_third_party(root, language):
    if language == 'en':
        title = 'Third-party software'
        text = (
            'Z80 CPU emulator: redcode/Z80\n'
            '© 1999–2025 Manuel Sainz de Baranda y Goñi\n'
            'GNU LGPL v3\nhttps://github.com/redcode/Z80\n\n'
            'Z80v2 example: © Bitrowz (ayssn)\n'
            'Original project: GNU GPL v3\n'
            'https://oshwhub.com/ayssn/z80-sbc-v2\n\n'
            'TP801 and TPBUG: © Beijing University of Technology\n\n'
            'C-BIOS 0.29: © BouKiCHi, Reikan, Maarten ter Huurne and contributors\n'
            'BSD 2-Clause; full notice: firmware/msx/README.cbios\n'
            'https://cbios.sourceforge.net/\n\n'
            'RainBIOS: © 2026 RainBIOS contributors, BSD 3-Clause\n'
            'Bundled BASIC and other notices: firmware/msx/rainbios/THIRD_PARTY_NOTICES.md\n'
            'https://github.com/salvogendut/rainbios\n\n'
            'Laser 310 original ROM and character generator: VTech and respective rights holders\n'
            'Source: https://github.com/bushy555/MESS_MAME_ROMS'
        )
    else:
        title = '第三方程序使用'
        text = (
            'Z80 CPU 模拟核心：redcode/Z80\n'
            '© 1999–2025 Manuel Sainz de Baranda y Goñi\n'
            'GNU LGPL v3\nhttps://github.com/redcode/Z80\n\n'
            'Z80v2 演示项目：© Bitrowz（立创开源社区：bitrowz）\n'
            '原项目使用 GNU GPL v3\n'
            'https://oshwhub.com/ayssn/z80-sbc-v2\n\n'
            'TP801 及 TPBUG：© 北京工业大学\n\n'
            'C-BIOS 0.29：© BouKiCHi、Reikan、Maarten ter Huurne 等贡献者\n'
            'BSD 2-Clause；完整声明：firmware/msx/README.cbios\n'
            'https://cbios.sourceforge.net/\n\n'
            'RainBIOS：© 2026 RainBIOS 贡献者，BSD 3-Clause\n'
            '所含 BASIC 等版权说明：firmware/msx/rainbios/THIRD_PARTY_NOTICES.md\n'
            'https://github.com/salvogendut/rainbios\n\n'
            'Laser 310 原机 ROM 和字模：VTech 及相关权利人\n'
            '来源：https://github.com/bushy555/MESS_MAME_ROMS'
        )
    messagebox.showinfo(title, text, parent=root)
