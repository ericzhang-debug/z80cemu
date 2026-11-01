# Z80-V2 屏幕输出版 CP/M

双击项目根目录 `start-cpm-screen.cmd`。显示输出同时送往 TMS9918A 和串口；点击视频窗口输入键盘字符，也可以使用串口输入。CF 默认只读，若要写入，请先在 CF 窗口明确启用写入，或将镜像复制后使用。

`loader.bin` 是启动 ROM，`cpm-screen-cf.img` 是 512 字节物理扇区 CF 镜像。源代码基于 `reference/source` 中 Bitrowz 的 Z80-V2 CP/M 程序，保留其署名和 GPLv3 许可证。修改包括启动时初始化显卡、BIOS 输出到屏幕、同时支持串口与屏幕键盘，并缓存键盘输入以避免状态查询消耗字符。

要重新构建，先保留或移走本目录已存在的输出镜像，然后执行 `build.cmd`。脚本需要本项目 `reference/source` 的原始源码、工具链和已构建的 `build/cpm/8mb-hd.dsk`；打包脚本不会覆盖已有输出镜像。
