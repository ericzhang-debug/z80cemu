"""Load an explicitly chosen local Python machine assembly script."""
import importlib.util
import sys
import uuid
from pathlib import Path

def load_machine(path):
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != '.py':
        raise ValueError('机器配置必须是 Python 文件')
    name = '_z80_machine_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise ValueError('无法加载机器脚本')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
        build = getattr(module, 'build', None)
        if not callable(build): raise ValueError('机器脚本必须定义 build()')
        result = build()
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError('build() 必须返回 (machine, clock_hz)')
        machine, clock = result
        if isinstance(clock, bool) or not isinstance(clock, int) or clock <= 0:
            raise ValueError('时钟频率必须是正整数')
        if not all(hasattr(machine, item) for item in ('components', 'cpu', 'io_history', 'io_counts')) or not all(
                callable(getattr(machine, item, None)) for item in ('step', 'reset')):
            raise ValueError('build() 返回的机器不满足平台接口')
        return machine, clock
    finally:
        sys.path.pop(0)
        sys.modules.pop(name, None)
