# 自定义机器与组件

## 项目结构与职责

`machines/*.py` 是用户可编辑的机器组装脚本，决定时钟、内存、器件实例、地址译码和信号连接。基础 CPU、RAM、ROM 位于 `components`；其他器件放在 `components/extends`，各器件互不导入。机器特有的总线或时序可以放在 `boards`，但不能写死在平台主界面中。`ui` 存放可复用的视图，器件也可实现自己的窗口。

应用通过“机器 → 打开机器配置”加载脚本，或者运行 `py -3.10 app.py --machine machines/文件名.py`。脚本是直接运行的 Python 代码，只应加载可信脚本。脚本必须定义 `build()`，返回 `(machine, clock_hz)`，时钟单位为 Hz。

## 组装一台机器

```python
from platform_core import Machine
from components.extends.z80_ctc import Z80CTC
from components.extends.z80_pio import Z80PIO

def build():
    memory = [
        {'name': 'ROM', 'type': 'rom', 'start': 0x0000, 'size': 0x2000},
        {'name': 'RAM', 'type': 'ram', 'start': 0x2000, 'size': 0xe000},
    ]
    machine = Machine({'memory': memory})
    machine.memory[0].load(bytes.fromhex('00 76'))
    ctc, pio = Z80CTC(0x10), Z80PIO(0x14)
    machine.attach_decoded_io('计时器', ctc, 0x10, 0xff, 4)
    machine.attach_decoded_io('并行接口', pio, 0x14, 0xff, 4)
    # 例：把 CTC 的第 0 个输出脉冲接到 PIO A 的选通输入。
    def pulse(channel, count):
        if channel == 0:
            for _ in range(count):
                pio.ports[0].set_strobe(False)
                pio.ports[0].set_strobe(True)
    ctc.pulse = pulse
    ctc.core.pulse = pulse
    machine.auto_open_windows = ['ROM', '计时器']  # None 为全部，[] 为不自动打开
    return machine, 1_000_000
```

内存地址是 16 位，`start` 和 `size` 为整数。一个芯片可用 `regions` 映射多个不连续窗口，每个区域包含 `start`、`size`、`offset`；例如将同一芯片的偏移 0 和 0x1000 分别映射到 0000H 和 2000H。不同器件区域不能重叠；需要银行切换时应提供自定义 `resolve_memory(address)`，使其返回当前选中的存储器。CPU 读取未映射地址返回 FFH。ROM 仅可通过内存窗口授权修改或初始化时加载。

`attach_io(name, device, ports)` 精确指定 16 位地址；`attach_decoded_io(name, device, base, mask, count)` 用地址掩码定义镜像。例如 `base=0x10, mask=0xff, count=4` 表示低八位 10H–13H，高八位任意。重复地址会报错；重名实例自动加序号。设备添加顺序决定支持菊花链设备的中断优先级。`machine.bind_keyboard(keyboard, screen)` 可把键盘输入绑定到屏幕等组件的窗口。

## 实现一个扩展器件

在 `components/extends` 下按器件名称新建 `.py`，不要导入其他扩展器件。最小 I/O 器件如下：

```python
class ExampleChip:
    pins = {'D0': 'bidirectional', '/CS': 'input', '/RD': 'input', '/WR': 'input'}

    def __init__(self):
        self.value = 0

    def read_port(self, address):
        return self.value

    def write_port(self, address, value):
        self.value = value & 0xff

    def reset(self):
        self.value = 0
```

`pins` 说明名称和方向；它不是自动生成的电路连接。需计时的部件可实现 `tick(cycles)`，每条 CPU 指令后收到经过的 T 状态数。简单共享中断可实现 `irq_active()`；有菊花链的器件还需实现 `candidate()`、`in_service()`、`acknowledge(candidate)` 和 `reti()`。信号可通过构造函数接收回调，或由机器脚本连接其公开方法。没有 `open_gui` 的部件不必有界面；需要界面时实现 `open_gui(root, pause)` 并返回 `tk.Toplevel`，修改存储内容或打开文件前调用 `pause()`。允许缩放的窗口可设置 `gui_resizable = True`。有其他生命周期需要时，可实现 `bind_ui(root, pause)`、`ui_tick()`、`close_ui()`；它不应依赖窗口已经打开。

## 重要边界与测试

默认执行模型是指令级，`tick` 在指令结束后执行；并非所有引脚均有周期精确波形。需要在 I/O 指令中途更新器件的机器，应在板级子类中明确实现并测试时序。界面不能直接执行第二套 CPU 循环，也不应由组件导入其他具体组件。状态变化须经总线或脚本定义的连接，关闭窗口不应影响模拟硬件。

平台默认逐指令执行。Z80-V2 对已验证的设备启用批量运行，并在 I/O 及中断截止时间同步器件；未明确支持的设备会使机器回退到逐指令执行。仅当设备的 `tick` 对任意分段都等价、I/O 副作用与中断时序已经验证时，才应声明 `batch_tick_safe`、`batch_io_safe` 和实现 `batch_irq_deadline()`；自定义组件不要为了提速随意声明这些属性。TP801 在 CTC 空闲时使用单独的加速路径，计时器工作或 PROM 等待时仍逐指令运行。实际频率受程序、设备、窗口刷新和主机性能影响，不保证任何配置均能达到目标值。

为新部件编写独立测试，覆盖地址译码、复位、输入输出、异常及信号连接；为整机写固件启动和操作测试。运行 `py -3.10 -m unittest discover -s tests`。`machines/tp801.py` 展示 TP801 的组装；其 ROM 使用仓库中的原始 TPBUG 固件，不以界面逻辑替代 CPU 执行。
