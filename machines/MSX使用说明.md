# MSX1 示例机器

双击 `start-msx.cmd` 启动 MSX1 示例。默认固件为开源 RainBIOS MSX1；启动后进入其内置的 Z80 BASIC。点击显卡窗口后可使用键盘，例如输入 `PRINT 2` 并回车。使用控制器窗口操作两个手柄。卡带窗口可加载不超过 32 KiB 的普通线性 ROM，加载或取出会暂停并复位机器；操作后点击主窗口“开始”。

`start-msx-cbios.cmd` 使用可再分发的 C-BIOS 0.29 和 Logo ROM。C-BIOS 不包含 BASIC、磁带或磁盘支持；没有游戏卡带时会显示提示。也可以在运行平台时通过“机器 → 打开机器配置”选择 `machines/msx.py` 或 `machines/msx_cbios.py`。

## 模拟的硬件与连接

- 3.579545 MHz Z80，16 KiB 页面粒度的四个主槽位：槽 0 放系统 ROM，槽 1 为普通卡带，槽 3 为 64 KiB RAM；未插入或未译码的槽位返回 FF。
- I8255 端口 A8–AB：主槽选择、国际布局键盘矩阵、模式 0 及 C 口逐位置位/复位。8255 模式 1/2 握手尚未实现。
- TMS9918A 端口 98/99：显示和帧中断；键盘与显卡窗口绑定。AY-3-8910 端口 A0–A2：三声道、噪声、包络和双手柄输入。声卡提供数字采样输出，未模拟模拟电路滤波和芯片总线等待。
- 磁带机与 8255 的 PC4 电机控制、PC5 写信号和 AY 端口 A bit 7 输入连接。程序启动磁带电机时，如果尚未装入磁带，平台会暂停并自动询问读取 WAV 或录制 WAV；选择成功后会显示文件名并提示点击主窗口“开始”继续。磁带窗口自动打开：播放时显示已读取的真实比例和时长，录制时由于总长度未知显示动态进度和已录时长。也可以手动打开磁带机窗口选择或取出磁带。录音在电机停止后保存；输入支持单声道/双声道 PCM WAV，输出为 44.1 kHz 8 位单声道 WAV。波形通过 Z80 固件的时序产生和解码，录制期间请不要关闭程序。
- 卡带目前只支持普通线性 ROM，不支持 Konami、ASCII 等银行切换 mapper。未实现 MSX 扩展槽、内存映射器和磁盘机；不能声称可运行所有游戏，也不能通过菜单使用这些未实现的外设。默认 RainBIOS 本身也是兼容性开发中的替代固件，并非原厂 MSX BASIC。

## 固件来源和许可

`firmware/msx/rainbios/rainbios_msx1.rom` 来自 [RainBIOS](https://github.com/salvogendut/rainbios) 的 `build/rainbios_msx1.rom`，检索时主线提交 `c55c75dcff6a0745cc54526d7e3a561cb641789c`，SHA-256 `12b3a887cfacb7e1e2657069f9ef780ef2cded06fb75188220ff3f193dcb4d5d`。RainBIOS © 2026 RainBIOS contributors，BSD-3-Clause。主 ROM 还包含 R. T. Russell 的 Z80 BASIC、ZX0、CC0 图像等独立授权内容；完整授权与版权通知见 `firmware/msx/rainbios/LICENSE`、`THIRD_PARTY_NOTICES.md` 和 `LICENSES/`。上游指出，公开发行时使用 BBC BASIC 名称需要另行取得许可或重命名，代码许可并不自动授予名称使用权。

`firmware/msx/cbios_main_msx1_eu.rom` 和 `cbios_logo_msx1.rom` 来自 [openMSX 随附的 C-BIOS](https://github.com/openMSX/openMSX/tree/master/Contrib/cbios)，BSD-2-Clause；原始版权声明和完整许可见 `firmware/msx/README.cbios`。

端口、键盘和槽位接线依据 [MSX Technical Data Book](https://www.msxarchive.nl/pub/msx/docs/manuals/msxtech.pdf)、[MSX I/O 端口](https://map.grauw.nl/resources/msx_io_ports.php) 和 [国际键盘矩阵](https://map.grauw.nl/articles/keymatrix.php)。

`tests/test_msx_machine.py` 用 Z80 执行两个真实固件：检查 C-BIOS 画面、插入测试卡带后经 BIOS 键盘输入及屏幕输出；RainBIOS 则经键盘输入 `PRINT 2` 并验证实际结果，通过固件的 TAPOON/TAPOUT 向 WAV 录制字节 42h，再通过 TAPION/TAPIN 从该 WAV 读回。还检查槽位、键盘、控制器和声音寄存器接线。
