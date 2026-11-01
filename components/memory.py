"""Byte-addressed memory components."""

class Memory:
    pins = {**{f'A{i}': 'input' for i in range(16)},
            **{f'D{i}': 'bidirectional' for i in range(8)},
            '/CS': 'input', '/OE': 'input', '/WE': 'input'}

    def __init__(self, name, start, size, readonly=False, regions=None):
        if size <= 0 or start < 0 or (regions is None and start + size > 65536):
            raise ValueError(f'{name}: invalid address range')
        self.name, self.start, self.size, self.readonly = name, start, size, readonly
        self.regions = regions or [{'start': start, 'size': size, 'offset': 0}]
        self.data = bytearray([0xff if readonly else 0] * size)

    def contains(self, address):
        for region in self.regions:
            if region['start'] <= address < region['start'] + region['size']: return True
        return False

    def offset(self, address):
        for region in self.regions:
            if region['start'] <= address < region['start'] + region['size']:
                return region['offset'] + address - region['start']
        raise ValueError(f'address {address:04X} is not mapped by {self.name}')

    def read(self, address):
        return self.data[self.offset(address)]

    def write(self, address, value):
        if not self.readonly:
            self.data[self.offset(address)] = value & 255

    def load(self, content, offset=0):
        if offset < 0 or offset + len(content) > self.size:
            raise ValueError('文件超出存储器范围')
        self.data[offset:offset + len(content)] = content
