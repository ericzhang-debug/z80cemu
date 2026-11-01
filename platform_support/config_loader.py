"""Read and validate the user-editable memory map."""
import json
from pathlib import Path

def load_memory(path):
    with Path(path).open('r', encoding='utf-8') as stream:
        data = json.load(stream)
    specs = data.get('memory')
    if not isinstance(specs, list) or not specs:
        raise ValueError('memory 必须是非空数组')
    result = []
    names = set()
    for spec in specs:
        if not isinstance(spec, dict) or spec.get('type') not in ('rom', 'ram'):
            raise ValueError('存储器类型必须是 rom 或 ram')
        name = spec.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('存储器名称必须非空')
        original = name
        index = 2
        while name in names:
            name = f'{original} ({index})'; index += 1
        names.add(name)
        def number(key):
            value = spec.get(key)
            if isinstance(value, bool): raise ValueError(f'{name}: {key} 无效')
            if isinstance(value, int): return value
            if isinstance(value, str):
                try: return int(value, 0)
                except ValueError: pass
            raise ValueError(f'{name}: {key} 无效')
        size = number('size')
        regions = spec.get('regions')
        if regions is None: regions = [{'start': spec.get('start'), 'size': size, 'offset': 0}]
        if size <= 0 or not isinstance(regions, list) or not regions:
            raise ValueError(f'{name}: 容量或区域无效')
        normalized = []
        for region in regions:
            def field(key, default=None):
                value = region.get(key, default)
                if isinstance(value, bool) or not isinstance(value, (int, str)):
                    raise ValueError(f'{name}: {key} 无效')
                try: return int(value, 0) if isinstance(value, str) else value
                except (ValueError, TypeError): raise ValueError(f'{name}: {key} 无效')
            start, length, offset = field('start'), field('size'), field('offset', 0)
            if start < 0 or length <= 0 or start + length > 65536 or offset < 0 or offset + length > size:
                raise ValueError(f'{name}: 地址范围或器件偏移无效')
            prior = [r for item in result for r in item['regions']] + normalized
            if any(start < r['start'] + r['size'] and r['start'] < start + length for r in prior):
                raise ValueError(f'{name}: 地址重叠')
            normalized.append({'start': start, 'size': length, 'offset': offset})
        result.append({'name': name, 'type': spec['type'], 'start': normalized[0]['start'], 'size': size, 'regions': normalized})
    return result
