# 开发流程

## 初始化状态

本次仅建立文档、Python 包元数据、PlatformIO 配置与目录骨架。没有安装依赖、运行 Python、执行构建/测试/本地烟测或烧录板子；没有可运行的 CLI 或固件。

## 环境与依赖

Python 使用 3.11+，先检查项目 `.venv`/`venv`，其次查 conda 环境，记录解释器绝对路径。使用系统 Python 前须经用户授权。需要安装依赖时先说明具体包和环境，请求安装；不通过自动下载工具隐式创建环境。

`pyproject.toml` 声明最小功能依赖 NumPy、OpenCV headless 和 tqdm；CLI 使用标准库 argparse。当前只给兼容范围，尚无经验证的锁文件；首次获准配置环境时解析并记录实际版本、Python 和 OS，再采用锁文件管理。不要声称现在已经完全可复现，也不要手写未解析的 lock 文件。

PlatformIO 工程在 `firmware/`，平台初始固定到 `renesas-ra@1.9.0`。VS Code 打开仓库根目录后，可将 `firmware/` 作为 PlatformIO 项目打开。当前尚无 `main.cpp`，不能编译出有效固件；不添加空 `setup()/loop()` 来制造功能已完成的印象。

首次构建需要用户已允许所需安装及验证；记录实际 PlatformIO Core、framework、FSP、工具链和板版本，再细化精确锁定。将来具备固件时，命令为 `pio run -d firmware -e uno_r4_wifi`，烧录另加 `-t upload`。本次不执行这些命令。

## 代码组织

- `firmware/src/boards/uno_r4_wifi/`：GPIO pair 映射、timer 配置和板级操作。
- `firmware/src/`：按需要加入入口和与板型无关的时序逻辑；`firmware/include/` 放真正共享的头文件。
- `src/camsync_check/`：分析库的 src layout；模块随功能落地，CLI 与核心计算分离。
- `profiles/boards/`：几何尺寸、LED 索引与编码能力；电气映射仍由固件板级模块负责。两者使用相同 board/profile 标识。
- `examples/`：通用图像输入描述示例，不绑定用户目录或采集系统。
- `docs/`：设计、协议、硬件来源和决策更新。

Python 使用类型注解与 4 空格缩进；C++ 使用 4 空格、明确整数宽度和单位后缀。机器文件和代码命名使用英文；解释性文档默认中文。

新增板型时，先提供板级实现和光学描述，再按已有实现中的共同需求抽象；不预建通用硬件插件框架。新增编码必须同步修改 firmware、decoder 约定及报告版本信息。

## 变更与证据

小幅、完整修改后提交，推荐 `docs:`、`chore:`、`feat:`、`fix:` 前缀。每次完成后说明改了什么、查阅了哪些依据、执行了哪些验证及未验证项。不自动 push。

科研项目默认不写或运行测试、本地烟测和模拟实验；有明确用户要求时再做相应验证。平时审阅文档一致性、来源和 Git diff 即可，不新增测试框架、pre-commit 或自动执行实验的 CI。

数据和报告存放在忽略目录 `data/`、`outputs/`。禁止提交真实采集画面、机器地址、凭据或用户私有路径。示例只包含虚构路径和公开硬件标识。

保留现有 LICENSE；从 Arduino 或其它上游引入源代码时单独核对许可、保留归属并记录来源 tag/commit。
