# camsync-check

使用 MCU 板载 LED 作为独立光学时间参考，离线检查多相机、多采集节点的实际曝光同步。

首个目标板为 **Arduino UNO R4 WiFi**；固件使用 **VS Code + PlatformIO + C++ / Arduino framework**，分析模块使用 **Python + OpenCV**，未来通过 `camsync-check` 命令行输出逐帧结果和报告。

当前阶段：**方案与项目初始化**。已有开发约定、工程布局和配置骨架；尚未实现发光固件、CV 解码或 CLI，也没有实测精度结论。

## 测量目标

- 相机间曝光时间偏差（camera-to-camera offset）。
- 不同节点所连接相机的曝光时间偏差（node-to-node optical offset）。
- 偏差随时间的波动、漂移，以及逐帧时间一致性。
- 以 250 µs、100 µs 为候选编码时隙，探索 sub-ms 测量能力；时隙不等于测量精度。

默认所有相机共同看到同一块板。软件时间戳仅辅助关联和诊断，不作为光学真值。独立运行的多块板不天然共享时间基准。

相机采集完全由用户负责。本仓库不接入相机 SDK、V4L2、Jetson 或树莓派控制程序；输入是用户保存的图像及描述它们的简单配置。首批使用 Arducam B0267，相关输入特征见[相机参考记录](docs/hardware/arducam-b0267-input.md)。

## 文档

- [总体方案与实施阶段](docs/design.md)
- [UNO R4 WiFi 硬件依据](docs/hardware/uno-r4-wifi.md)
- [光学编码与数据约定草案](docs/protocol.md)
- [开发流程与依赖管理](docs/development.md)
- [开发者及 AI agent 约定](AGENTS.md)

## 工程结构

```text
firmware/                 PlatformIO 工程、公共时序代码、板级实现
src/camsync_check/        Python 分析库，未来 CLI 只做编排
profiles/boards/          板型的光学布局与能力描述
examples/                采集配置示例
docs/                    方案、协议、硬件依据、开发流程
data/                    本地采集数据（忽略，不入 Git）
outputs/                 本地分析产物（忽略，不入 Git）
```

保留仓库现有 [GPL v3 许可证文本](LICENSE)。
