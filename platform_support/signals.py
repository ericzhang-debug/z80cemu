"""Explicit digital signal nets for devices that opt into pin-level wiring."""
class SignalConflict(ValueError):
    pass

class Net:
    def __init__(self, name, pull=1):
        if pull not in (0, 1, None): raise ValueError('invalid pull value')
        self.name, self.pull = name, pull
        self.drivers = {}
        self.listeners = []
        self.value = pull

    def connect(self, listener):
        self.listeners.append(listener)
        listener(self.value)

    def drive(self, source, value):
        """Set a driver to 0, 1 or None (high impedance); reject contention."""
        if value not in (0, 1, None): raise ValueError('invalid signal value')
        updated = dict(self.drivers); updated[source] = value
        driven = {v for v in updated.values() if v is not None}
        if len(driven) > 1: raise SignalConflict(f'{self.name}: conflicting drivers')
        result = next(iter(driven)) if driven else self.pull
        self.drivers = updated
        if result != self.value:
            self.value = result
            for listener in tuple(self.listeners): listener(result)
