# MCU Firmware

PlatformIO project root. Configuration exists, but no buildable or flashable firmware is implemented yet.

The first target is RA4M1-driven slow localization and 250 µs single-LED scanning on UNO R4 WiFi. Board-specific GPIO/timer code belongs in `src/boards/uno_r4_wifi/`; add common sequencing to `src/` and shared headers to `include/` as needed.

Retain the official ESP32-S3 firmware. Do not run ArduinoLEDMatrix scanning alongside this project's driver. See [development conventions](../AGENTS.md) and [hardware evidence](../docs/hardware/uno-r4-wifi.md).
