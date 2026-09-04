# Arduino UNO R4 WiFi 核对记录

核对日期：2026-09-04。以下是文档/源码核对，不是板上验证。

## 板级事实

UNO R4 WiFi（ABX00087）采用 48 MHz RA4M1，带 12 × 8 板载 LED 矩阵及 ESP32-S3。首版仅开发 RA4M1 固件，保留 ESP32-S3 的官方板级功能。USB-C 用于供电和上传。

官方资料：

- [Arduino 产品与资源入口](https://docs.arduino.cc/hardware/uno-r4-wifi/)
- [官方 schematic](https://docs.arduino.cc/resources/schematics/ABX00087-schematics.pdf)
- [官方 datasheet](https://docs.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf)
- [RA4M1 Hardware Manual](https://www.renesas.com/en/document/mah/renesas-ra4m1-group-users-manual-hardware)，重点检查 I/O ports、GPT、AGT 章节。

矩阵由 11 个 RA4M1 GPIO 以 Charlieplexing 连接，没有智能 LED 控制器。官方矩阵逻辑索引 `0..95` 对应 8 行、12 列；板的图像方向必须通过定位采集确认。

| 矩阵引脚索引 | Arduino 内部索引 | MCU 引脚 |
| --- | --- | --- |
| 0 | 28 | P003 |
| 1 | 29 | P004 |
| 2 | 30 | P011 |
| 3 | 31 | P012 |
| 4 | 32 | P013 |
| 5 | 33 | P015 |
| 6 | 34 | P204 |
| 7 | 35 | P205 |
| 8 | 36 | P206 |
| 9 | 37 | P212 |
| 10 | 38 | P213 |

来源：[ArduinoCore-renesas 1.6.0 variant.cpp](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/variants/UNOWIFIR4/variant.cpp)。这些是内部索引，不代表外部排针编号。

## 官方扫描实现的含义

依据：[ArduinoCore-renesas 1.6.0 Arduino_LED_Matrix.h](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/libraries/Arduino_LED_Matrix/src/Arduino_LED_Matrix.h)。

- `pins[96][2]` 定义每颗 LED 的 source/sink 引脚对；第一项驱动高，第二项驱动低。
- `turnLed()` 先清除矩阵相关输出方向，再通过 PFS 配置目标引脚。
- `begin()` 配置 10000 Hz 周期 timer；ISR 每次只处理一个 LED，并按模 96 递增索引。
- 由此推算：单槽 100 µs，完整扫描 9.6 ms，固定像素约 104.17 Hz 重访。10 kHz 不是整屏刷新率。

这些证据支持自定义单灯时序的可行性，但没有给出 ISR 延迟分布、光学边沿抖动或相机解码精度。

## 工具链

使用 PlatformIO `platform = renesas-ra@1.9.0`、`board = uno_r4_wifi`、`framework = arduino` 作为初始配置。平台版本来自[官方 v1.9.0 发布](https://github.com/platformio/platform-renesas-ra/releases/tag/v1.9.0)；[该版本 manifest](https://github.com/platformio/platform-renesas-ra/blob/v1.9.0/platform.json)声明 UNO Arduino framework `~1.6.0`。

这是初始选型，尚未安装或构建验证。平台固定并不等于所有间接包精确锁定；首次授权构建时记录实际 framework、工具链、PlatformIO Core 和 FSP 版本，核对其源码与本文引用版本的一致性。

[PlatformIO 板卡文档](https://docs.platformio.org/en/latest/boards/renesas-ra/uno_r4_wifi.html)列出默认 `sam-ba` 上传及板载 CMSIS-DAP 调试支持。USB 供电/上传与断点调试应分开记录：调试仍依赖连接固件、驱动及工具配置，当前尚未实测。官方 [USB bridge 源码](https://github.com/arduino/uno-r4-wifi-usb-bridge)可追溯 ESP32-S3 侧功能；本项目不因此引入 ESP32-S3 开发任务。

## 实现前核对项

- 固定并保留 96 个 LED 的映射来源、source/sink 方向与物理方向。
- 查明使用的 timer 通道和外围时钟频率；不把 CPU 的 48 MHz 自动当作 timer 输入频率。
- 检查 framework 已使用/保留的 timer、USB 和 SysTick 中断对关键路径的影响。
- 核对高阻切换、PFS 保护、跨端口顺序、blanking 与其它 GPIO 状态的保留。
- 按 schematic、电气额定值和实际占空比核对点亮方式，尤其是定位模式和重复点亮。
- 记录板版本、bootloader/连接固件版本（可取得时）及实测限制。

不在初始化阶段复制 96 项第三方映射或编写未经验证的寄存器操作。
