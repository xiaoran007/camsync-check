# Measurement Design

## Scope and timing chain

All compared cameras observe one stationary UNO R4 WiFi target. Two B0267 synchronization boards provide four views each; their acquisition nodes may be identical or different. Each visible view is decoded independently. No acquisition code belongs in this repository.

```text
GPT event -> bounded ISR -> RA4M1 GPIO -> LED pulse -> camera exposure
          -> saved images -> automatic R4 grid -> binary slot interval -> offsets
```

The nominal slot is 250 µs. A fixed asymmetric permutation visits each physical LED once per 96-slot, 24 ms cycle. The canonical table is in the packaged R4 profile; PlatformIO generates its C++ header from that same file. Protocol `r4-permuted96-v1` must match both firmware and analysis. The permutation breaks geometric orientation symmetry; it does not resolve cycle epochs.

The firmware uses GPT with PCLKD, divider 1, integer period counts, and interrupt priority 2. It reuses ArduinoCore-renesas 1.6.0 `ArduinoLEDMatrix.on()/off()` for the official mapping and direct GPIO operations. It never starts the official scanner. Only one LED conducts at once; each LED retains 1/96 nominal duty. The corner diagnostic preserves this duty by pulsing one corner once per cycle and advancing corners every 21 cycles.

GPIO transitions follow timer interrupts rather than a direct timer-to-pin peripheral route. ISR latency, transition blanking, and oscillator error remain in the timing chain. Serial status reports clock frequency, channel, counts, and ISR count, but neither calibrates the oscillator nor detects every missed timer event. Successful compilation is not timing or electrical validation. No hardware flashing or scientific validation has been performed.

## Automatic geometry and decoding

For each configured camera crop, inspect up to `localization.max_frames` evenly spaced source frames. Temporal maximum-minus-minimum projection suppresses static texture. Connected components provide candidate LED centers; OpenCV orders a complete symmetric 12 × 8 circle grid. Fit a homography using all centers and reject excessive residuals or undersampled LEDs. No manual corners are required.

Four row/column reversal hypotheses describe the remaining grid symmetries. For each, sample the selected frames, reorder physical LED signals into the protocol's slot order, and count valid contiguous intervals. Single lit LEDs do not establish orientation. Require sufficient valid frames and a configured margin over the runner-up. An ambiguous orientation or incomplete grid invalidates that camera's measurements and remains visible in the report. This method assumes stationary geometry, sufficient phase coverage, separated LED spots, and one intended target per view.

Each LED is sampled in its original camera coordinates: mean brightness within 0.22 of the local grid pitch, minus median background in an annulus from 0.32 to 0.44 pitch. Binary decoding rejects signals near threshold, excessive saturation, no lit LEDs, nearly full cycles, or disconnected lit intervals in slot order. Thresholds are acquisition-dependent and must be inspected using the saved signals and overlays. No per-LED gain or fractional-pulse brightness model is fitted.

Counting illuminated LEDs estimates an exposure span. Their identities in the known scan order establish the start/end phase needed for synchronization. Exposure metadata is optional and never replaced with an assumed duration. Automatic exposure may vary between frames; each is decoded separately. Initial quantitative support is limited to a contiguous global-shutter exposure shorter than one cycle, without HDR/temporal blending. Rolling shutter needs a separate line-timing model and is rejected by this implementation.

## Conditional timing bounds

Let `q` be the slot duration, `s` the first observed slot, `k` the count of observed slots, and `b` the allowed number of missed boundary slots per camera. Under correct geometry, no false lit slots, and no interior holes:

```text
exposure start is in [(s - b) q, (s + 1) q]
exposure end   is in [(s + k - 1) q, (s + k + b) q]
```

The implementation uses interval midpoints as phase estimates and reports conservative exposure-duration bounds. Pairwise start offset has half-width `(b + 1) q`: 500 µs with `q = 250 µs` and `b = 1`. This supports the initial 1 ms goal conditionally; it does not establish measured accuracy. Boundary detection assumptions, GPIO timing, and clock-scale error require later empirical validation. Observed jitter includes quantization and image-decoding error.

Offsets are `start_other - start_reference`, positive when the other exposure starts later. Enumerate cycle shifts and retain a unique solution under the explicit prior `|offset| < 10000 µs`. Reject competing cycles, unsupported offsets, and intervals crossing the prior boundary; never clip an interval to manufacture precision. This prior comes from the user's independent check and cannot be verified by this repeating target. An actual error displaced by 24 ms may alias to an apparently small offset.

Configured `pass_tolerance_us` produces per-pair pass/fail/inconclusive decisions from the full conditional interval. It is separate from slot duration and target resolution. Invalid or missing pairs do not pass, and the tool makes no global pass claim from partial coverage.

## Two-board results

For every supplied source-frame pair `(n, m)`, compare all four A views against all four B views: 16 cross-board pairs. For each source image retain six within-board pairs. Report explicitly selected representative cameras for board/node comparison, without substituting another camera or averaging away sensor skew. Images cannot independently separate node-clock error, camera latency, and transport delay.

Frame pairs are explicit, monotonic, one-to-one zero-based indices into the ordered input lists. The checker does not rematch frames to minimize offset. Unpaired indices are reported as unmatched, not diagnosed as dropped captures. Per-frame phase steps are modulo 24 ms and cannot certify full frame intervals or identify whole-cycle losses.

Report median offset, sample standard deviation, P95 absolute residual from the median, peak-to-peak range, valid coverage, and drift per reference frame index. Optional configured frame period scales drift to µs/second with that provenance. No smoothing is applied. One valid pair cannot estimate jitter; fewer than three cannot estimate the reported drift. Four cameras on one board and their shared target are not independent clocks.

## Evidence and references

The user's `bapd8_acquisition` repository was inspected read-only at `b44b38b86d96990898676464ad7de7ef06ce0d0a` on 2026-09-04. `docs/hardware_b0267_camera_kit.md`, `docs/hardware_jetson_orin_nano.md`, and `rpi/capture_sync_frame_pair.py` record OV9281 monochrome global-shutter sensors and a 5120 × 800 GREY composite of four 1280 × 800 views. Connector-to-image-slot mapping is unverified. Its exposure requests and unresolved driver-control units do not establish the exposure of user-provided images. These records are provenance, not runtime dependencies.

- [UNO R4 WiFi hardware](https://docs.arduino.cc/hardware/uno-r4-wifi/), [schematic](https://docs.arduino.cc/resources/schematics/ABX00087-schematics.pdf), and [datasheet](https://docs.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf).
- [ArduinoCore-renesas 1.6.0 LED mapping and GPIO implementation](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/libraries/Arduino_LED_Matrix/src/Arduino_LED_Matrix.h), [FspTimer implementation](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/cores/arduino/FspTimer.cpp), and [board pins](https://github.com/arduino/ArduinoCore-renesas/blob/1.6.0/variants/UNOWIFIR4/variant.cpp).
- [RA4M1 Hardware Manual](https://www.renesas.com/en/document/mah/renesas-ra4m1-group-users-manual-hardware): I/O ports, GPT, and AGT.
- [PlatformIO board support](https://docs.platformio.org/en/latest/boards/renesas-ra/uno_r4_wifi.html) and [platform 1.9.0 manifest](https://github.com/platformio/platform-renesas-ra/blob/v1.9.0/platform.json).
- [OpenCV circle-grid detection and homography API](https://docs.opencv.org/4.11.0/d9/d0c/group__calib3d.html).
- [Arducam OV9281](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/Global-Shutter/1MP-OV9281-OV9282/).
