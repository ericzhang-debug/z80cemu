"""Basic ROM component."""
from .memory import Memory

class ROM(Memory):
    def __init__(self, name, start, size, regions=None):
        super().__init__(name, start, size, readonly=True, regions=regions)
