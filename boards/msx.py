"""MSX1 primary slots. All devices and wiring are provided by the machine."""
from platform_core import Machine
from components.ram import RAM
from components.rom import ROM

class MSX1(Machine):
    def __init__(self):
        super().__init__({'memory': []})
        self.allow_batched_execution = True
        self.bios = ROM('C-BIOS 主 ROM', 0, 0x8000)
        self.logo = ROM('C-BIOS Logo ROM', 0x8000, 0x4000)
        self.ram = RAM('MSX RAM', 0, 0x10000)
        self.memory = [self.bios, self.logo, self.ram]
        self.components.extend(self.memory)
        self.slots = 0
        self.cartridge = None

    def resolve_memory(self, address):
        slot = (self.slots >> (2 * (address >> 14))) & 3
        if slot == 3: return self.ram
        if slot == 0:
            if address < 0x8000: return self.bios
            if address < 0xc000: return self.logo
        if slot == 1 and self.cartridge and self.cartridge.contains(address): return self.cartridge
        return None

    def read(self, address):
        device = self.resolve_memory(address)
        return device.read(address) if device else 0xff

    def write(self, address, value):
        device = self.resolve_memory(address)
        if device: device.write(address, value)

    def reset(self):
        self.slots = 0
        super().reset()
