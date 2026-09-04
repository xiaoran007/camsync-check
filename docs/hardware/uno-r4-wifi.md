# Arduino UNO R4 WiFi Evidence

Reviewed on 2026-09-04 using documentation and source code, without hardware validation.

## Board facts

UNO R4 WiFi (ABX00087) combines a 48 MHz RA4M1, a 12 × 8 LED matrix, and an ESP32-S3. Initially develop only RA4M1 firmware and retain the ESP32-S3's official board functions. USB-C supplies power and supports uploading.

Primary references:

- [Arduino product and resources](https://docs.arduino.cc/hardware/uno-r4-wifi/)
- [Official schematic](https://docs.arduino.cc/resources/schematics/ABX00087-schematics.pdf)
- [Official datasheet](https://docs.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf)
- [RA4M1 Hardware Manual](https://www.renesas.com/en/document/mah/renesas-ra4m1-group-users-manual-hardware), particularly I/O ports, GPT, and AGT.

Eleven RA4M1 GPIOs drive the Charlieplexed matrix without an intelligent LED controller. Logical indices 0–95 describe eight rows and twelve columns; localization must establish image orientation.

| Matrix pin index | Arduino internal index | MCU pin |
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

Source: [ArduinoCore-renesas 1.6.0 variant.cpp](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/variants/UNOWIFIR4/variant.cpp). These are internal indices, not external header labels.

## Official scanner behavior

Source: [ArduinoCore-renesas 1.6.0 Arduino_LED_Matrix.h](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/libraries/Arduino_LED_Matrix/src/Arduino_LED_Matrix.h).

- `pins[96][2]` identifies each LED's high source and low sink.
- `turnLed()` clears matrix output directions before configuring the selected pair through PFS.
- `begin()` configures a 10000 Hz periodic timer. Each ISR processes one LED and advances modulo 96.
- Consequently, a slot is nominally 100 µs and a full scan takes 9.6 ms, revisiting each pixel at approximately 104.17 Hz. The 10 kHz value is not a full-matrix refresh rate.

This supports investigating custom single-LED sequencing. It does not establish interrupt latency, optical jitter, or decoder accuracy.

## Toolchain

Initial configuration uses `platform = renesas-ra@1.9.0`, `board = uno_r4_wifi`, and `framework = arduino`. See the [official v1.9.0 release](https://github.com/platformio/platform-renesas-ra/releases/tag/v1.9.0) and its [manifest](https://github.com/platformio/platform-renesas-ra/blob/v1.9.0/platform.json), which declares UNO Arduino framework `~1.6.0`.

This selection is not installation or build validation. Pinning the platform does not pin every transitive package. At the first authorized build, record resolved framework, compiler, PlatformIO Core, and FSP versions and compare installed source with the references above.

[PlatformIO's board page](https://docs.platformio.org/en/latest/boards/renesas-ra/uno_r4_wifi.html) lists default `sam-ba` upload and onboard CMSIS-DAP debugging. Treat power/upload and breakpoint debugging separately: debugging depends on connectivity firmware, drivers, and configuration, and has not been verified here. The official [USB bridge source](https://github.com/arduino/uno-r4-wifi-usb-bridge) provides ESP32-S3 provenance without introducing an ESP32-S3 development task.

## Before implementation

- Establish all 96 LED mappings, source/sink polarity, and physical orientation.
- Identify the timer channel and peripheral clock; do not assume the CPU clock is the timer input.
- Review framework timer reservations and interference from USB and other interrupts.
- Check high-impedance transitions, PFS protection, multi-port write ordering, blanking, and preservation of unrelated GPIO state.
- Review duty cycles and electrical limits, especially slow localization or repeated illumination of one LED.
- Record board revision, available bootloader/connectivity-firmware versions, and measured limitations.

Do not copy a third-party mapping or implement unverified register operations during initialization.
