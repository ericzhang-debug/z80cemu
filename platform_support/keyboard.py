"""Translate Tk's shifted US keyboard symbols to their physical key names."""

SHIFTED_KEYS = dict(zip(
    ('exclam', 'at', 'numbersign', 'dollar', 'percent', 'asciicircum',
     'ampersand', 'asterisk', 'parenleft', 'parenright', 'underscore',
     'plus', 'braceleft', 'braceright', 'bar', 'colon', 'quotedbl',
     'asciitilde', 'less', 'greater', 'question'),
    ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'minus',
     'equal', 'bracketleft', 'bracketright', 'backslash', 'semicolon',
     'apostrophe', 'grave', 'comma', 'period', 'slash'),
))


def physical_keysym(key):
    key = key.lower()
    return SHIFTED_KEYS.get(key, key)
