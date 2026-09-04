# 光学编码与输入/输出约定草案

状态：draft，尚无解析器或固件实现。协议正式冻结时单独递增版本，不以项目版本替代。

## 标识与单位

- `board_id`：发光板型号，首个为 `uno_r4_wifi`。
- `target_id`：物理发光板身份；与相机聚合板 ID 分开。
- `protocol_id`：光学序列，例如候选 `sweep96-v0`；算法/序列语义变更需新版本。
- `run_id`：一次连续的发光运行，复位后改变；它不等于跨系统共享时钟。
- `camera_id`、`node_id`、`source_id`：分别标识相机视图、采集节点、源图像序列。
- 物理网格索引 `led_id = row * 12 + column`，零起点；图像方向由定位记录明确。
- 数据时间字段后缀写明 `_ticks`、`_us`、`_ns`；缺失使用 `null`，不以 0 表示未知。

## 固件运行描述（未来导出）

包含 firmware commit、board/profile/protocol 版本及 hash、run ID、序列参数与周期、timer 类型/通道/时钟源/输入频率/分频/周期计数、名义 slot 时间、导通与 blanking、启动/停止条件、检测到的 overrun 及标定状态。

只提供 ISR 计数不能证明未漏硬件周期；overrun 的检测方法及检测不到的情况须记录。换算微秒时保留时钟是否经过外部标定的信息。

v0 的全局 slot 递增，对应 `led_id = slot_index % 96`。从图像只能确定周期内时间时，输出 `phase_only` 和周期，不能补造 epoch。v1 的生成规则、光学起始标识与消歧条件尚待 M3 冻结。

## 输入：用户提供的图像

CLI 计划使用 `camsync-check analyze --input capture.json --output outputs/run-name`。这是设计中的接口，目前不可执行。

`capture.json` 描述已有图像及最少的分组信息，不要求任何相机 SDK 或采集服务。核心库计划也接受调用方已加载的图像数组与同等元数据。

| 内容 | 必需性/规则 |
| --- | --- |
| 格式版本、发光板型、编码标识、slot 参数 | 定量解码必需，可来自所刷固件的配置；不强求有串口日志 |
| `sources[].frames` | 有序图像路径列表；相对路径以配置文件所在目录解析 |
| `cameras[]` | camera/node/source ID 及可选 crop；完整图像省略 crop |
| `shutter` | global、rolling 或 unknown；未知不能默认为 global |
| `exposure_us` 与来源 | 可未知；已知时区分 requested、reported、calibrated；逐帧值优先于常量 |
| 软件时间戳、driver frame ID | 可选，仅辅助；提供时记录时钟域和语义 |
| 帧关联 | 用户明确的 capture-group ID 可作为被检查的配对；不能从相同文件序号推断跨节点同时曝光 |
| 几何/亮度校准 | 定量解码需要对应校准，可单独文件提供 |
| 判定阈值 | 可选；没有阈值只报告测量，不给 pass/fail |

拼接图通过 `crop_xywh` 表达任意通用矩形视图，无 B0267 专属驱动。保留源帧 ID 和各视图 ID；同一源帧中的视图可以直接构成待检查的相机组。输入缺少时间顺序时，只支持单帧结果，不能计算连续帧 jitter 或 drift。

只有孤立帧或缺少曝光元数据也可进入分析，但可能只能返回亮灯位置、相位候选/区间及失败原因。不能保证任意一批图片都能恢复唯一的完整时间轴。

## 输出计划

- `frames.csv`：camera/source/frame ID、时间估计类型、曝光起点/中点、区间下上界、曝光值及来源、周期/epoch 状态、质量与失败原因。
- `pairs.csv`：相机对与匹配帧 ID、匹配依据、偏差、区间/不确定度、未匹配状态；单独保留用户原有配对与算法推断配对。
- `summary.json`：版本、配置与数据标识、相机/节点指标、有效样本数、覆盖率、失败计数、阈值、判定与限制。
- `report.html`：离线可读报告，包含逐帧偏差曲线、相机对偏差矩阵、有效率、异常定位图及方法说明；机器数值以 CSV/JSON 为准。

区间默认称为“可行区间”；只有明确的统计模型与覆盖率证据时才称为置信区间。不同相机共享的参考误差具有相关性，不能无条件按独立误差平方和合并。

完整失败不得用 0 µs 填充。典型原因：`target_not_visible`、`saturated`、`insufficient_signal`、`ambiguous_epoch`、`unknown_exposure`、`unsupported_shutter`、`unmatched_frame`。逐帧无效属于测量输出；配置错误或文件读取失败则显式终止该次任务并给出位置。
