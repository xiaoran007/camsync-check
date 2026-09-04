# Measurement Design

This document contains measurement rationale and evidence. Usage, configuration selection, and build instructions live in the root README. Firmware and analysis remain unimplemented.

## Reference and scope

Compared cameras observe one stationary UNO R4 WiFi target. The primary use case is two B0267 synchronization boards, each supplying four camera views. The boards may share one acquisition node or use separate nodes; board identity and node identity are independent. At least one selected camera on each board must see the same target. Full eight-camera diagnostics require target visibility in all eight views. Non-overlapping views need a separate shared-reference design.

Images measure exposure relationships. They cannot independently separate operating-system clock error, camera-internal latency, and transport delay. Node results are optical offsets between explicitly selected representative cameras or a documented aggregation.

```text
MCU timer -> GPIO sequence -> LED light -> camera exposure integration
          -> user-provided images -> geometry/photometry -> timing -> report
```

The firmware runs independently of host scheduling. Serial commands may configure a run, but their arrival times are not ground truth. A reset begins a new run; record firmware/profile/protocol identity and available run metadata.

## Firmware and encoding

Start with a GPT periodic event, a short ISR, and precomputed single-LED source/sink operations. Retain Arduino board support while reviewing FSP/register operations on the critical path. Record clock source, divider, timer counts/channel, interrupt priority, conduction, blanking, and overrun detection limits. ISR latency remains part of the timing chain.

At most one LED is driven per slot. Disable the previous pair before enabling the next, preserve unrelated pins, and review electrical limits for scanning and slow localization. Do not extrapolate scan duty cycles to continuous illumination. DTC/DMAC optimizations require separate evidence and are not initial commitments.

The official matrix implementation advances one of 96 LEDs per 10 kHz timer interrupt. A nominal 100 µs slot therefore gives a 9.6 ms full scan, not a simultaneously updated 96-bit timestamp. Physical orientation must be established during localization.

| Stage | Encoding | Result and limitation |
| --- | --- | --- |
| v0 | Fixed 96-LED sweep, initially 250 µs, later 100 µs | Within-cycle phase; 24 ms / 9.6 ms periods leave whole-cycle ambiguity |
| v1 candidate | Precisely specified long-period single-LED position sequence, jointly decoded over frames | Full offsets only if competing epochs are distinguishable under exposure integration |

For example, 0.2 ms and 9.8 ms offsets can share phase in a 9.6 ms sweep. Label v0 results `phase_only`; never use them to claim absence of whole-frame errors. A long-period pseudorandom sequence is a candidate, not a proven solution: integration discards event order. Freeze generation rules, seed, period, optical start identification, search range, and observation requirements only after establishing identifiability. Do not invent epochs or guess ambiguous matches.

## Image model and decoding

Camera profiles explicitly define dimensions, channels, dtype, shutter type, and crops. The run configuration supplies paths, identity mappings, and exposure provenance. Unknown or inconsistent settings are not guessed.

Use a slow localization sequence or explicit corners and orientation to establish the grid. High-speed frames need not show all corners. Correct significant distortion using supplied intrinsics; preserve original sensor coordinates. Estimate background and per-LED responses from suitable calibration images, then extract unsaturated intensities.

Implementation proceeds from a configured wide-image crop to a per-camera target ROI. Fit the planar grid from explicit correspondences with OpenCV homography functions; project 96 LED sampling regions into the original image rather than measuring brightness only after resampling. A diagnostic rectified image is useful for review. For each LED, integrate its foreground region, subtract local background, and normalize by its calibrated response. Each frame becomes a 96-element intensity vector, not merely a list of thresholded bright spots. Use intensity fitting against the known sequence to estimate the exposure window; use multiple frames to reject temporal aliases without smoothing away frame-level jitter.

For a global-shutter observation of LED j:

```text
I_j = background_j + gain_j * integral(L_j(t), t_start, t_start + exposure) + noise_j
```

`L_j(t)` includes the actual conduction window. Prefer known exposure. Estimate exposure jointly only when identifiable; unknown values may produce only feasible intervals or an inconclusive result. Saturation, gamma, compression, and automatic exposure affect the model. Long exposures can erase repeated-cycle phase; short exposures may identify a slot without resolving its interior.

Prioritize global-shutter inputs. Rolling-shutter quantitative results require known/calibrated line timing and scan direction: `t_start(y) = t_start(y_ref) + (y - y_ref) * line_time`. Account for ROI offsets, rotation, and resizing, and use column coordinates for column-scanning sensors. Otherwise report unsupported timing rather than applying a global-shutter model.

Associate frames monotonically using optical evidence and explicit correspondence constraints. A source frame containing multiple views defines a group to inspect, not proof of simultaneity. Preserve user-supplied groups separately from inferred matches; unrestricted nearest-time matching must not hide whole-frame offsets. Unordered batches support individual observations, not continuous jitter or drift estimates.

## Metrics and reporting

Default to exposure midpoint. Define `delta_ab = t_b - t_a`, positive when B exposes later. Report median offset, sample standard deviation and P95 absolute residual after median removal, peak-to-peak residual range, and sample counts. Fit drift separately; detrended jitter supplements original statistics. Report optical inter-frame intervals and missing/duplicate/unmatched candidates without treating file indices as hardware counters.

Report cross-node camera pairs before representative-camera node summaries. Aggregation must state its method and prerequisites. MCU ticks and nominal microseconds remain distinguishable; an uncalibrated oscillator is not a traceable absolute clock. Camera agreement or internal MCU timing alone cannot establish 100 µs accuracy.

## Two-board comparison

Decode each of the four views independently for every source frame. For a supplied pair of source frames `(n, m)`, retain all valid cross-board differences `delta_ij(n, m) = t_Bj(m) - t_Ai(n)`: up to 16 comparisons. Also retain six within-board pairs per board, so a single sensor's optical skew is not hidden by a board-wide average.

The default board summary is the offset between explicitly configured representative cameras, labeled with their identities. Never silently replace a missing representative. Once within-board timing consistency is established, an explicitly selected median-of-camera-times summary may be added; it is an operational board timestamp, not proof that every exposure was simultaneous. Shared reference errors and four views from one source frame are not independent observations.

Keep two questions separate: (1) how far apart the exposures in the acquisition system's supplied pairs were, and (2) which frames are closest in independently decoded optical time. The first diagnoses the system's pairing; the second requires explicit optical-association output with unmatched/duplicate candidates. Without a shared capture index or trigger, frame zero on one board does not define frame zero on the other. Cyclic phase and whole-frame displacement must remain separate; v0 alone cannot resolve arbitrary whole-cycle offsets.

Per-board-pair reports include representative-camera offset versus time, median offset, jitter, drift, unmatched frames, and the 4 × 4 cross-board offset matrix when all views are visible. A single matched image pair provides a timing comparison; jitter and drift require an ordered sequence. Do not infer a node clock error merely because the cameras are attached to different nodes.

Planned artifacts are `frames.csv`, `pairs.csv`, `summary.json`, and an offline `report.html`. Include resolved configuration/profile snapshots, versions, frame associations, feasible intervals, rejection reasons, valid coverage, and limits. Call intervals confidence intervals only with a justified statistical model. Shared reference errors need not be independent.

Acceptance criteria are user-supplied; a 250 µs slot is not a pass threshold. Use `pass`, `fail`, or `inconclusive` only with defined criteria and adequate coverage/uncertainty. Missing measurements never become 0 µs. Routine use requires no extra electronics; externally calibrated accuracy claims may require a separate calibration campaign.

## Initial B0267 evidence

At the user's request, `bapd8_acquisition` was inspected read-only on 2026-09-04 at HEAD `b44b38b86d96990898676464ad7de7ef06ce0d0a`. Relevant records: `docs/hardware_b0267_camera_kit.md`, `docs/hardware_jetson_orin_nano.md`, and `rpi/capture_sync_frame_pair.py`. They are provenance, not runtime dependencies.

That project records four monochrome global-shutter OV9281 sensors, a 5120 × 800 GREY composite with four 1280 × 800 horizontal views, and an observed mode near 44.972 fps. Physical connector-to-slot mapping is unverified. The Jetson `exposure=681` control has unresolved units; it must not become 681 µs. An RPi script requests 4000 µs, which is not evidence of actual exposure for another dataset. At an actual 4 ms exposure, 250 µs slots span roughly 16 slot durations and require integration-based decoding.

Its phone-display check found no visible internal offset at approximately 8.33–10 ms method resolution, not sub-ms proof. The built-in profile describes only the confirmed wide-image mode; other modes need explicit profiles.

## Next steps and references

Implement slow localization and the 250 µs sweep, then image geometry/photometry and v0 phase decoding. Establish a distinguishable v1 sequence before full offset reports. Add 100 µs operation and rolling-shutter support only with appropriate evidence. Execute scientific validation only when explicitly requested.

- [UNO R4 WiFi hardware](https://docs.arduino.cc/hardware/uno-r4-wifi/), [schematic](https://docs.arduino.cc/resources/schematics/ABX00087-schematics.pdf), and [datasheet](https://docs.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf).
- [ArduinoCore-renesas 1.6.0 LED mapping/scanner](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/libraries/Arduino_LED_Matrix/src/Arduino_LED_Matrix.h) and [board pin mapping](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/variants/UNOWIFIR4/variant.cpp).
- [RA4M1 Hardware Manual](https://www.renesas.com/en/document/mah/renesas-ra4m1-group-users-manual-hardware): I/O ports, GPT, and AGT.
- [PlatformIO board support](https://docs.platformio.org/en/latest/boards/renesas-ra/uno_r4_wifi.html) and [renesas-ra 1.9.0 package manifest](https://github.com/platformio/platform-renesas-ra/blob/v1.9.0/platform.json). Compare installed packages with referenced source at the first authorized build.
- [Arducam OV9281](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/Global-Shutter/1MP-OV9281-OV9282/) and [Basler shutter timing](https://docs.baslerweb.com/electronic-shutter-types).
