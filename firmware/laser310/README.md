# Laser 310 示例

双击 `start-laser310.cmd`，或运行 `py -3.10 app.py --machine machines/laser310.py`。
点击视频窗口后可用 PC 键盘输入；如输入没有反应，请先点击画面。PC 方向键分别映射为原机 CTRL 与 M、逗号、句号、空格的组合键（左、右、上、下）。Backspace 和 Delete 映射为原机 CTRL+M，向左退一格，随后输入可覆盖该位置。

示例使用 3.546894 MHz Z80、16 KiB BASIC ROM、2 KiB 视频 RAM 和 16 KiB 用户 RAM。`6800H–6FFFH` 是键盘及视频/磁带控制地址，`7000H–77FFH` 是显存，`7800H–B7FFH` 是用户 RAM。机器组装位于 `machines/laser310.py`，板级译码位于 `boards/laser310.py`，器件位于 `components/extends`。

## 磁带

在 BASIC 中执行 `CLOAD` 或 `CSAVE`，会自动暂停并要求选择读取或录制的 WAV 文件。成功选择后会显示文件名及操作提示，同时打开磁带进度窗口；点击主窗口“开始”继续。读取进度按 WAV 样本及模拟 CPU 周期计算；录制总长度事先未知，因此显示动态进度条和已录时长。输入和输出使用 CPU 周期计时的磁带信号，由原 BASIC 程序处理磁带数据。读取支持 8/16 位、单声道或立体声 PCM WAV，录制输出 8 位单声道 PCM WAV；录制结束自动保存，也可以在磁带组件窗口手动停止。暂不支持 CAS 或 VZ 文件。取消对话框后可以恢复运行，按原机 BREAK 退出命令，返回 BASIC 后下一次命令可以重新选择。

## 固件来源

本机使用的 `vtechv20.u12` 及字符字模 `vtech1.chr` 提取自 [bushy555/MESS_MAME_ROMS 的 roms.all.zip](https://github.com/bushy555/MESS_MAME_ROMS/blob/main/roms.all.zip)。BASIC 固件的 SHA-1 为 `f216c266bc09b0dbdbad720796e5ea9bc7d91e53`，与 [MAME Laser 310 定义](https://github.com/mamedev/mame/blob/master/src/mame/vtech/vtech1.cpp)一致。字模 SHA-1 为 `56503d26f3d71c55b4d88706b0e90453eb8d5755`。这些是历史机器固件/字模，来源没有声明自由再分发许可；其版权归原权利人所有，不能据此认为是开源软件。

真实 BASIC 固件启动、键盘输入和 `CSAVE`/`CLOAD` WAV 往返有自动测试：`py -3.10 -m unittest tests.test_laser310 -v`。扬声器根据原机锁存器位 0、5 的差分电平产生音频。MC6847 使用帧级渲染，颜色为数字近似，不模拟复合视频、逐扫描线修改和所有扩展显示模式。

键盘组合参考 [VZ 系列键盘说明](https://www.vz200.org/bushy/articles/20210310%20Bob%20Kitch%20VZ-VERBATIM%20Vol%202%20401p%20reduced.pdf) 与 [MAME 的按键矩阵](https://github.com/mamedev/mame/blob/master/src/mame/vtech/vtech1.cpp)。

## 打印机

启动示例时会打开虚拟打印机窗口。原厂 BASIC 可以直接使用 `LPRINT "HELLO"` 输出文字、`LLIST` 或 `LLIST 10-20` 列印程序，以及 `COPY` 输出当前屏幕。窗口中的纸张从机器启动起持续记录，关闭窗口或复位机器不会清除；可手动清空、保存 UTF-8 文本，或保存原始打印字节。取消“联机”会让打印机报告忙碌，重新联机后固件可以继续输出。

接口连接至低 8 位 I/O 端口 00h、0Dh 和 0Eh，状态和数据由真实 BASIC 固件处理。虚拟纸张支持普通文字、回车、换行、退格、制表及换页；其他控制码仍保存在原始数据中。`COPY` 的文字屏幕已验证，GP-10 专用图形打印命令和物理打印机输出尚未模拟。关于命令与图形打印限制，可参阅 [VZ-300 使用手册](https://www.two-mag.com/cpc/ACME/_BONUS/8_BITS/VTECH%5BHKG%5D/1985_LASER_310%28VZ300%29/VZ300_Main_unit_manual%5BENG%5D.pdf)。
