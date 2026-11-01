"""Small 8-bit ATA task-file subset for a raw CompactFlash disk image."""
from pathlib import Path

class CompactFlash:
    def open_gui(self, root, pause):
        from ui.cf_window import open_cf_window
        return open_cf_window(root, self, pause)
    batch_io_safe = True
    pins = {'D0-D7': 'bidirectional', 'A0-A2': 'input', '/CS0': 'input',
            '/IORD': 'input', '/IOWR': 'input', '/RESET': 'input'}
    SECTOR = 512

    def __init__(self, base, image=None, readonly=False):
        self.base = base
        self.image = None
        self.readonly = readonly
        self.sectors = 0
        if image is not None:
            self.mount(image, readonly)
        else:
            self.reset()

    def mount(self, image, readonly=True):
        """Validate before changing media; discard any in-flight ATA command."""
        path = Path(image)
        size = path.stat().st_size
        if size == 0 or size % self.SECTOR or size // self.SECTOR > 0x10000000:
            raise ValueError('CF 镜像必须为 512 字节整数倍，且最多 128 GiB')
        if not path.is_file():
            raise ValueError('CF 镜像必须是普通文件')
        # Check accessibility before replacing a previously mounted image.
        with path.open('rb'):
            pass
        if not readonly:
            with path.open('r+b'):
                pass
        self.image, self.readonly = path, bool(readonly)
        self.sectors = size // self.SECTOR
        self.reset()

    def eject(self):
        self.image = None
        self.sectors = 0
        self.reset()

    def reset(self):
        self.reg = [0, 0, 1, 0, 0, 0, 0xe0, 0x40 if self.image is not None else 0x00]
        self.error = 0; self.buffer = bytearray(); self.pos = 0
        self.operation = None; self.remaining = 0

    def lba(self):
        return self.reg[3] | self.reg[4] << 8 | self.reg[5] << 16 | (self.reg[6] & 15) << 24

    def fail(self, code=4):
        self.error = code; self.reg[7] = 0x41; self.operation = None
        self.buffer.clear(); self.pos = 0

    def prepare(self):
        if not (self.reg[6] & 0x40) or self.lba() >= self.sectors:
            self.fail(0x10); return
        try:
            if self.operation == 'read':
                with self.image.open('rb') as f:
                    f.seek(self.lba() * self.SECTOR); self.buffer = bytearray(f.read(self.SECTOR))
                if len(self.buffer) != self.SECTOR: self.fail(); return
            else: self.buffer = bytearray(self.SECTOR)
            self.pos = 0; self.reg[7] = 0x48
        except OSError: self.fail()

    def next_sector(self):
        self.remaining -= 1
        self.reg[2] = self.remaining & 255
        address = self.lba() + 1
        self.reg[3:6] = [address & 255, address >> 8 & 255, address >> 16 & 255]
        self.reg[6] = (self.reg[6] & 0xf0) | (address >> 24 & 15)
        if self.remaining: self.prepare()
        else: self.operation = None; self.reg[7] = 0x40

    def identify(self):
        data = bytearray(512)
        def word(index, value):
            data[index * 2:index * 2 + 2] = (value & 0xffff).to_bytes(2, 'little')
        def ata_string(index, count, value):
            raw = value.encode('ascii')[:count * 2].ljust(count * 2, b' ')
            for n in range(0, len(raw), 2):
                data[index * 2 + n:index * 2 + n + 2] = raw[n:n + 2][::-1]
        word(0, 0x848a); word(49, 0x0200)
        word(60, self.sectors); word(61, self.sectors >> 16)
        ata_string(10, 10, 'Z80SIM0001')
        ata_string(23, 4, '0.1')
        ata_string(27, 20, 'Z80SIM VIRTUAL CF')
        self.buffer = data; self.pos = 0; self.operation = 'identify'; self.reg[7] = 0x48

    def read_port(self, address):
        reg = (address - self.base) & 7
        if self.image is None: return 0xff
        if reg == 1: return self.error
        if reg != 0: return self.reg[reg]
        if self.operation not in ('read', 'identify') or not self.reg[7] & 8: return 0xff
        value = self.buffer[self.pos]; self.pos += 1
        if self.pos == self.SECTOR:
            if self.operation == 'identify': self.operation = None; self.reg[7] = 0x40
            else: self.next_sector()
        return value

    def write_port(self, address, value):
        reg = (address - self.base) & 7; value &= 255
        if self.image is None: return
        if reg == 0:
            if self.operation != 'write' or not self.reg[7] & 8: return
            self.buffer[self.pos] = value; self.pos += 1
            if self.pos == self.SECTOR:
                try:
                    with self.image.open('r+b') as f:
                        f.seek(self.lba() * self.SECTOR); f.write(self.buffer)
                except OSError: self.fail(); return
                self.next_sector()
        elif reg == 7:
            self.error = 0
            if value == 0x04:
                self.reset()
            elif value in (0x20, 0x30):
                if value == 0x30 and self.readonly: self.fail(); return
                self.operation = 'read' if value == 0x20 else 'write'
                self.remaining = self.reg[2] or 256; self.prepare()
            elif value == 0xef and self.reg[1] == 1:
                self.operation = None; self.reg[7] = 0x40
            elif value == 0xec: self.identify()
            elif value == 0xe7: self.operation = None; self.reg[7] = 0x40
            else: self.fail()
        else: self.reg[reg] = value
