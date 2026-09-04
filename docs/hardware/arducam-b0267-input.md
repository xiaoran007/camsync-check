# Initial Image Source: Arducam B0267

These notes describe input characteristics, not camera integration. At the user's request, the external `bapd8_acquisition` working tree was inspected read-only on 2026-09-04; its HEAD was `b44b38b86d96990898676464ad7de7ef06ce0d0a`. Observations below come from that project's records, not new measurements in this repository.

Reference files in the external repository:

- `docs/hardware_b0267_camera_kit.md`
- `docs/hardware_jetson_orin_nano.md`
- `jetson/camera.py`
- `scripts/capture_board_sync.py`
- `rpi/capture_sync_frame_pair.py`

These files are provenance references, not runtime dependencies.

## Relevant evidence

| Item | Existing evidence | Analysis implication |
| --- | --- | --- |
| Sensors | Four monochrome OV9281 global-shutter sensors through UC-512 | Prioritize global-shutter grayscale input |
| Layout | 5120 × 800 GREY, four horizontal 1280 × 800 views | Accept explicit crops or already-separated images |
| Identity | Physical connector-to-slot mapping remains unverified | Use user-defined camera IDs; do not infer connector numbers |
| Cadence | Some recorded modes measured approximately 44.972 fps | Do not equate requested 45 fps with actual cadence |
| Jetson exposure | Initial V4L2 `exposure` value 681; units unresolved | Preserve raw control value; never interpret it as 681 µs |
| RPi example | Script requests 4000 µs and records `ExposureTime` metadata | Separate requested exposure from reported exposure; a default is not a measurement |
| Internal synchronization | No visible difference in a 120 Hz phone-display check, with approximately 8.33–10 ms method resolution | Still measure all four optical offsets independently |

Sharing one source frame or exposure control does not prove precise simultaneity.

## Input boundary

Users provide per-camera image sequences or wide frames with explicit `[x, y, width, height]` crops. For the confirmed 5120 × 800 layout, x offsets are 0, 1280, 2560, and 3840. Do not apply this layout to other image dimensions automatically.

The checker never connects to cameras or changes exposure. Prefer lossless grayscale images. Compression, saturation, and varying exposure must be documented and reflected in decoding quality. Missing exposure metadata still permits localization and intensity extraction; quantitative timing is available only when identifiable, otherwise the result is inconclusive.

If actual exposure is 4 ms, a 250 µs sequence spans approximately 16 slots during exposure, with partial boundary slots as applicable. This conditional calculation explains why intensity integration matters; a frame cannot generally be treated as one illuminated LED.

Manufacturer sensor reference: [Arducam OV9281 global shutter](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/Global-Shutter/1MP-OV9281-OV9282/). Bundle layout remains grounded in actual images and the records above.
