# camsync-check

An independent optical timing reference and offline analysis tool for measuring actual exposure synchronization across cameras and acquisition nodes.

The first target is **Arduino UNO R4 WiFi**. Firmware uses **VS Code + PlatformIO + C++ with the Arduino framework**. The analysis library uses **Python + OpenCV**, with a planned `camsync-check` CLI.

**Status: design and project initialization.** This repository contains development conventions, design documents, and configuration scaffolding. Firmware, decoding, and the CLI are not implemented; no timing accuracy has been measured.

## Scope

- Camera-to-camera exposure offset.
- Optical exposure offset between cameras attached to different nodes.
- Synchronization jitter, drift, and frame-level timing consistency.
- Candidate optical slots of 250 µs and 100 µs; slot duration is not measurement accuracy.

All cameras initially observe the same physical LED target. Host timestamps are auxiliary metadata, not optical ground truth. Independently running targets do not automatically share a clock.

Users handle acquisition. This repository accepts saved images and simple input descriptions; it does not integrate camera SDKs, V4L2, Jetson, Raspberry Pi, or another acquisition repository. The first image source is Arducam B0267; see the [input notes](docs/hardware/arducam-b0267-input.md).

## Documentation

- [System design and milestones](docs/design.md)
- [UNO R4 WiFi hardware evidence](docs/hardware/uno-r4-wifi.md)
- [Optical protocol and data contract draft](docs/protocol.md)
- [Development workflow](docs/development.md)
- [Contributor and agent instructions](AGENTS.md)

## Layout

```text
firmware/                 PlatformIO project and board-specific firmware
src/camsync_check/        Python analysis library and future CLI
profiles/boards/          Optical geometry and board capabilities
examples/                Image input descriptions
docs/                     Design, protocol, hardware, and development notes
data/                    Local captures, ignored by Git
outputs/                 Local analysis artifacts, ignored by Git
```

The repository retains its existing [GPL v3 license text](LICENSE).
