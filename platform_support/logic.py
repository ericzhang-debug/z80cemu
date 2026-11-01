"""Combinational logic helpers; values are integers, not electrical nets."""
def decoder(value, width, enabled=True, active_low=True):
    if width < 1 or not 0 <= value < (1 << width):
        raise ValueError('invalid decoder input')
    result = [False] * (1 << width)
    if enabled: result[value] = True
    return tuple(not bit for bit in result) if active_low else tuple(result)

def multiplexer(inputs, select):
    if not 0 <= select < len(inputs): raise ValueError('invalid selector')
    return inputs[select]
