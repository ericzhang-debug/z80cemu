"""Basic RAM component."""
from .memory import Memory

class RAM(Memory):
    def __init__(self, name, start, size, regions=None):
        super().__init__(name, start, size, readonly=False, regions=regions)
