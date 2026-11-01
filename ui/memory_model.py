"""Side-effect-free debugger access to the machine's active memory mapping."""
def check_range(start, length):
    if not isinstance(start, int) or not isinstance(length, int) or start < 0 or length <= 0 or start + length > 0x10000:
        raise ValueError('地址范围必须位于 0000–FFFF，长度必须大于 0')

def snapshot(machine, start, length):
    check_range(start, length)
    result = []
    for address in range(start, start + length):
        device = machine.resolve_memory(address)
        result.append((device.read(address) if device else 0xff,
                       'rom' if device and device.readonly else 'ram' if device else 'unmapped'))
    return result

def write_bytes(machine, start, data, allow_rom=False):
    check_range(start, len(data))
    operations = []
    for index, value in enumerate(data):
        address = start + index
        device = machine.resolve_memory(address)
        if device is None: raise ValueError(f'{address:04X} 没有映射存储器')
        if device.readonly and not allow_rom: raise ValueError(f'{address:04X} 是 ROM，请先勾选允许修改 ROM')
        operations.append((device, device.offset(address), value))
    for device, offset, value in operations:
        device.data[offset] = value

def prepare_import(data, length=None, fill=0):
    if length is None: length = len(data)
    if not isinstance(length, int) or length <= 0 or length > 65536: raise ValueError('导入长度必须在 1–65536 之间')
    if fill not in (0, 255): raise ValueError('填充值必须为 00 或 FF')
    return data[:length].ljust(length, bytes([fill]))
