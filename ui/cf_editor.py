"""Non-destructive sector editing for raw CompactFlash images."""
from pathlib import Path
import shutil

SECTOR = 512

class CFImageEditor:
    """Stage changes in memory; exporting always creates a new image."""
    def __init__(self, device):
        self.device = device
        self.changes = {}

    def mount(self, path, readonly=True):
        self.device.mount(path, readonly)
        self.changes.clear()

    def eject(self):
        self.device.eject()
        self.changes.clear()

    def sector(self, number):
        if not isinstance(number, int) or not 0 <= number < self.device.sectors:
            raise ValueError('扇区号超出镜像范围')
        if number in self.changes:
            return bytes(self.changes[number])
        with self.device.image.open('rb') as source:
            source.seek(number * SECTOR)
            result = source.read(SECTOR)
        if len(result) != SECTOR: raise OSError('读取扇区失败，镜像可能已被修改')
        return result

    def edit(self, number, data):
        if len(data) != SECTOR: raise ValueError('扇区必须恰好为 512 字节')
        self.sector(number)  # Validate address and medium before accepting edits.
        self.changes[number] = bytes(data)

    def import_bytes(self, offset, data):
        if not isinstance(offset, int) or offset < 0 or offset + len(data) > self.device.sectors * SECTOR:
            raise ValueError('导入数据超出镜像范围')
        # Work on a copy so failures cannot leave a partially staged import.
        staged = {}
        cursor = 0
        while cursor < len(data):
            absolute = offset + cursor
            index, within = divmod(absolute, SECTOR)
            piece = min(SECTOR - within, len(data) - cursor)
            content = bytearray(self.sector(index))
            content[within:within + piece] = data[cursor:cursor + piece]
            staged[index] = bytes(content)
            cursor += piece
        self.changes.update(staged)

    def export(self, destination):
        if self.device.image is None: raise ValueError('尚未加载 CF 镜像')
        destination = Path(destination)
        if destination.resolve() == self.device.image.resolve():
            raise ValueError('请另存为新文件，不能覆盖当前镜像')
        # Open exclusively before copying; cleanup only a file created here.
        with self.device.image.open('rb') as source:
            with destination.open('xb') as output:
                try:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                    for sector, data in self.changes.items():
                        output.seek(sector * SECTOR); output.write(data)
                except Exception:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise

def create_blank_image(destination, sectors):
    if isinstance(sectors, bool) or not isinstance(sectors, int) or not 1 <= sectors <= 0x10000000:
        raise ValueError('扇区数量必须在 1 到 268435456 之间')
    with Path(destination).open('xb') as output:
        output.truncate(sectors * SECTOR)
