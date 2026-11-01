"""Platform UI language and per-user settings; device labels stay device-owned."""
import json
import os
from pathlib import Path


_EN = {
    'Z80模拟': 'Z80 Simulator', '机器': 'Machine', '打开机器配置…': 'Open machine configuration…',
    '退出': 'Exit', '运行': 'Run', '单步': 'Step', '复位': 'Reset',
    '设置频率（{clock} MHz）…': 'Set frequency ({clock} MHz)…',
    '查看': 'View', 'CPU 寄存器': 'CPU registers', 'I/O 端口': 'I/O ports',
    '设置语言': 'Language', '关于': 'About', '第三方程序使用': 'Third-party software',
    '运行控制': 'Run control', '机器组件  ·  双击打开': 'Machine components  ·  Double-click to open',
    '运行中': 'Running', '暂停': 'Paused', '开始': 'Start', '暂停按钮': 'Pause',
    '实际频率：{frequency:.3f} MHz': 'Actual frequency: {frequency:.3f} MHz',
    '系统频率': 'System frequency', '输入频率（MHz）：': 'Enter frequency (MHz):',
    '频率错误': 'Invalid frequency', '请输入大于 0 且精确到 1 Hz 的频率（MHz）。': 'Enter a positive frequency in MHz, precise to 1 Hz.',
    '选择机器组装脚本': 'Select machine assembly script', 'Python 机器脚本': 'Python machine scripts',
    '机器加载失败': 'Machine load failed', '运行错误': 'Simulation error',
    '语言设置错误': 'Language settings error', '无法保存语言设置：{error}': 'Could not save language setting: {error}',
    ' 寄存器': ' registers', 'I/O 端口监视': 'I/O port monitor', '器件端口映射': 'Device port mapping',
    '显示已连接器件及其端口，包括尚未访问的端口。': 'Connected devices and their ports, including ports not yet accessed.',
    '实时访问与查询': 'Live activity and search', '端口（十六进制，留空显示已访问端口）': 'Port (hex; leave blank for accessed ports)',
    '显示完整 16 位地址': 'Show full 16-bit address', '端口': 'Port', '对应器件': 'Device',
    '最近操作': 'Last operation', '数值': 'Value', '访问次数': 'Accesses',
    '按低 8 位汇总；高 8 位不同的访问计入同一端口。': 'Grouped by low 8 bits; accesses with different upper bits share a port.',
    '请输入 00 到 {maximum} 之间的十六进制端口。': 'Enter a hexadecimal port from 00 to {maximum}.',
    '未映射': 'Unmapped', '读': 'Read', '写': 'Write',
    '（低 8 位；高 8 位任意）': ' (low 8 bits; any upper 8 bits)',
    '内存监视器': 'Memory monitor', '起始地址（十六进制）': 'Start address (hex)',
    '长度（十六进制）': 'Length (hex)', '允许修改 ROM': 'Allow ROM editing',
    'RAM 蓝　ROM 黄　未映射 灰；双击修改': 'RAM blue; ROM yellow; unmapped gray. Double-click to edit.',
    '范围错误': 'Invalid range', '修改内存': 'Edit memory',
    '地址 {address:04X}，输入两位十六进制数：': 'Address {address:04X}: enter two hexadecimal digits:',
    '请输入两位十六进制数': 'Enter two hexadecimal digits', '修改失败': 'Edit failed',
    '二进制文件': 'Binary files', '所有文件': 'All files', '导出失败': 'Export failed', '读取失败': 'Read failed',
    '导入二进制': 'Import binary', '长度（十六进制，留空自动）': 'Length (hex; blank for automatic)',
    '文件长度：{length} 字节；长度较短时截取，较长时填充': 'File: {length} bytes; truncate or pad to the requested length.',
    '填充值': 'Fill byte', '导入失败': 'Import failed', '导入': 'Import',
    '应用范围': 'Apply range', '导入 BIN': 'Import BIN', '导出 BIN': 'Export BIN',
    '地址范围必须位于 0000–FFFF，长度必须大于 0': 'The address range must be within 0000–FFFF and length must be positive',
    '导入长度必须在 1–65536 之间': 'Import length must be between 1 and 65536',
    '填充值必须为 00 或 FF': 'Fill must be 00 or FF',
    '启动失败': 'Startup failed', '必须指定机器配置脚本': 'A machine assembly script is required',
    '机器配置必须是 Python 文件': 'The machine configuration must be a Python file',
    '无法加载机器脚本': 'Unable to load the machine script',
    '机器脚本必须定义 build()': 'The machine script must define build()',
    'build() 必须返回 (machine, clock_hz)': 'build() must return (machine, clock_hz)',
    '时钟频率必须是正整数': 'The clock frequency must be a positive integer',
    'build() 返回的机器不满足平台接口': 'The machine returned by build() does not implement the platform interface',
    '键盘和目标组件必须先挂载': 'Attach the keyboard and target component first',
    '键盘组件必须提供 key_event，目标必须是另一组件': 'The keyboard must provide key_event and the target must be another component',
    '键盘与窗口已绑定': 'The keyboard and window are already bound',
    '同一部件实例不能重复挂载': 'The same component instance cannot be attached twice',
    '无效的 I/O 译码': 'Invalid I/O decoding',
    '基地址包含未译码位或超出范围': 'The base address contains undecoded bits or is out of range',
    'CPU 总线回调失败；当前指令可能已部分执行': 'CPU bus callback failed; the current instruction may have partially executed',
    '文件超出存储器范围': 'The file exceeds the memory range',
}


def translate(text, language='zh', **kwargs):
    return (_EN.get(text, text) if language == 'en' else text).format(**kwargs)


def translate_error(error, language='zh'):
    text = str(error)
    if language != 'en': return text
    if text.endswith(' 没有映射存储器'):
        return text.split(' ', 1)[0] + ' has no mapped memory'
    if text.endswith(' 是 ROM，请先勾选允许修改 ROM'):
        return text.split(' ', 1)[0] + ' is ROM; enable ROM editing first'
    for prefix, replacement in (('未知存储器类型: ', 'Unknown memory type: '),
                                ('内存地址重叠: ', 'Overlapping memory addresses: ')):
        if text.startswith(prefix): return replacement + text[len(prefix):]
    if text.endswith(': I/O 地址冲突或无效'):
        return text[:-len('I/O 地址冲突或无效')] + 'I/O address conflicts or is invalid'
    return _EN.get(text, text)


def settings_path():
    base = os.environ.get('APPDATA') if os.name == 'nt' else os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else Path.home() / '.config') / 'Z80SimPlatform' / 'settings.json'


def load_language():
    try:
        data = json.loads(settings_path().read_text(encoding='utf-8'))
        language = data.get('language') if isinstance(data, dict) else None
        return language if language in ('zh', 'en') else 'zh'
    except (OSError, ValueError, TypeError):
        return 'zh'


def save_language(language):
    if language not in ('zh', 'en'): raise ValueError('Unsupported language')
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict): data = {}
    except (OSError, ValueError, TypeError):
        data = {}
    data['language'] = language
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()
