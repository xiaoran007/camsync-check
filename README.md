# camsync-check

UNO R4 WiFi LED firmware and a Python CLI for checking camera synchronization from saved images. Camera acquisition stays outside this repository.

**Status:** initial implementation; firmware compiles in Docker. Image decoding, automatic localization, and timing accuracy have not been validated with captures or hardware. The initial goal is approximately 1 ms checks under an independently established offset prior of less than 10 ms.

## Build and run

Firmware builds use the shared Dev Container, through VS Code's **Reopen in Container** or Make:

```sh
make image                       # Build the environment
make dev                         # Open a container shell
make firmware                    # Compile UNO R4 WiFi firmware
```

The environment pins its Debian Bookworm base image by digest, PlatformIO Core 6.1.18, `renesas-ra@1.9.0`, and ArduinoCore-renesas 1.6.0. Linux amd64 is used, including emulation on ARM hosts. The completed build used GCC 7.2.1. Build products are in `firmware/.pio/build/uno_r4_wifi/`; packages are cached in `.cache/platformio/`. Transitive dependencies are not exhaustively locked.

Compilation stays in Docker; uploading runs on the host through Arduino CLI without USB passthrough. On macOS, install the host tools once, with installation authorized:

```sh
brew install arduino-cli
arduino-cli core update-index
arduino-cli core install arduino:renesas_uno@1.6.0
```

Connect the UNO R4 WiFi with a USB data cable. From the repository root:

```sh
make ports                                    # Find the board's actual port
make firmware                                 # Build the current source in Docker
make upload PORT=/dev/cu.usbmodemXXXX           # Replace with the actual port
make monitor PORT=/dev/cu.usbmodemXXXX          # Serial monitor at 115200 baud
```

The host commands use the project `.venv/bin/python` and require `arduino-cli` on PATH. An executable elsewhere can be selected with `ARDUINO_CLI=/path/to/arduino-cli`. The wrapper only supports `BOARD=uno_r4_wifi`; it requires an explicit port for upload/monitor and never guesses among connected devices. `make upload` writes the existing `firmware/.pio/build/uno_r4_wifi/firmware.bin` to RA4M1, replacing its current application and retaining the ESP32-S3 bridge firmware. It does not rebuild, install dependencies, or retry after failure. Missing or empty firmware is rejected; rebuild after source changes to avoid uploading a stale artifact. Close the serial monitor before uploading again.

If upload cannot reach the board, double-press RESET just after power-up, run `make ports` again, and retry with the reported port. See the [official board datasheet](https://docs-content.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf) and [Arduino CLI upload reference](https://docs.arduino.cc/arduino-cli/commands-reference/arduino-cli_upload).

After boot, the target runs without a serial connection: one LED per 250 µs slot, with all 96 LEDs visited once per 24 ms cycle. Serial at 115200 accepts `?` for JSON status, `s` for the measurement sequence, `c` for a slow corner-identification diagnostic, and `d` for dark. Check `ready: true`, `protocol: "r4-permuted96-v1"`, and `mode: "sweep"`. Use `s` throughout a capture; mode changes and resets interrupt the sequence. Exit the monitor with Ctrl-C.

Python uses the project `.venv` exclusively. With dependency installation authorized:

```sh
.venv/bin/python -m pip install -e .
.venv/bin/camsync-check --config configs/two-b0267.json
```

The CLI automatically locates the R4 matrix, decodes images, and writes an offline HTML report, CSV measurements, JSON summaries, and diagnostic PNGs. Progress goes to stderr; stdout prints the report path. Exit status 0 means processing completed, not that synchronization passed. Invalid measurements remain invalid. Choose a fresh output directory for each run.

## Configure inputs

Copy the [single-board example](configs/example.json) or [two-board example](configs/two-b0267.json), replace the fictional image paths, and list your ordered captures. Supply enough different optical phases to observe all 96 LEDs. The short example lists illustrate structure; they do not guarantee enough data for localization.

- **Profiles** define hardware and image layout. `builtin:b0267` describes 5120 × 800 uint8 grayscale images split into four horizontal 1280 × 800 views. `builtin:uno_r4_wifi` defines the target, protocol, and shared scan-order table.
- **Sources** identify each synchronization board, acquisition node, camera views, and ordered image paths. Camera IDs must be globally unique. Two boards can share a `node_id`. Camera ID mappings describe image slots, not an inferred physical connector mapping.
- **Comparison** selects two sources, their representative cameras, and explicit zero-based `frame_pairs`. These are the acquisition system's pairs to inspect. Equal file indices are not automatically assumed to mean simultaneous exposures.
- **Localization** controls how many evenly distributed source frames to inspect (`max_frames`, default example 48). Orientation needs at least `min_valid_frames` informative intervals and an `orientation_margin` advantage over other grid orientations. No ROI coordinates are required.
- **Analysis** defines background-subtracted on/off thresholds, saturation rejection, allowed missed boundary slots, the offset prior, and an optional `pass_tolerance_us`. `target_resolution_us` limits the conditional pair half-width; it does not certify accuracy.

All paths resolve relative to the run configuration. A complete user camera profile can replace a built-in reference with a file path, such as `./my-camera.json`; use the same schema as the [B0267 profile](src/camsync_check/profiles/b0267.json). A single camera has one full-image crop. The initial decoder requires global-shutter uint8 grayscale images. Dimensions, dtype, shutter model, and camera identity are never guessed or silently converted.

Exposure metadata may be `{"value_us": null, "provenance": "unknown"}`. Known values carry `requested`, `reported`, or `calibrated` provenance. Metadata is recorded, not used as an exact exposure constraint. The decoder estimates slot-level exposure boundaries independently for each frame, without brightness fitting or an assumed 4 ms exposure. Optional source `frame_period_us` only scales a drift slope into µs/second; it is not optical ground truth.

## Automatic R4 localization

Keep the board and cameras stationary and the full matrix visible in every view you want to compare. Across selected frames, the tool computes per-pixel maximum minus minimum brightness to suppress static background, detects bright components, and fits the known 12 × 8 grid with OpenCV. Sampling stays in original image coordinates. The minimum LED spacing is 6 pixels; homography residuals above 20% of horizontal LED pitch are rejected. Keep the target large and in focus, with background separation and modest perspective/lens distortion.

The rectangular grid alone cannot distinguish mirrored or reversed numbering. Firmware therefore uses a fixed asymmetric LED permutation, shared with Python through the target profile. The tool selects the orientation whose observed LEDs form contiguous intervals in this scan order. This preserves fixed intervals and the 24 ms cycle; it adds no long-period code or exposure fitting.

Localization requires all 96 positions to appear in the temporal projection and several informative multi-LED intervals. Repeated identical phases, very short or near-cycle exposures, occlusion, motion, saturation, and strong background activity can prevent it. A failed view is explicitly excluded with its reason; its offset never becomes zero. The report includes projection/grid overlays and `localization.json`. No manual ROI or alternative detector is silently substituted.

## Results

`report.html` shows the representative-camera offset, observed jitter, coverage, per-camera statistics, and the 4 × 4 cross-board median matrix. Each board also retains its six within-board camera pairs. A representative is never silently replaced. Node-to-node comparison uses the selected cameras' optical offsets, not inferred host-clock error.

| Artifact | Contents |
| --- | --- |
| `frames.csv` | Per-camera validity, first/last scan slots, start/end phase, exposure bounds, modulo phase step |
| `led_signals.csv` | Background-subtracted signals in physical row-major LED order |
| `pairs.csv` | Supplied frame associations, offsets, conditional bounds, rejection reasons, optional decisions |
| `summary.json` | Median, observed jitter SD, P95 residual, range, drift, coverage, versions, limitations |
| `resolved.json` | Configuration, profiles, and localization snapshot |
| `localization.json`, `localization/`, `diagnostics/` | Located geometry, orientation evidence, and review images |

Positive offset means the other camera starts exposure later. The default one-slot boundary allowance gives a conditional pair half-width of 500 µs. These are model bounds, not statistical confidence intervals or calibrated hardware accuracy. The 24 ms repetition cannot expose arbitrary whole-cycle/frame errors; the less-than-10-ms prior must come from independent evidence. See [measurement design](docs/design.md).

## Repository conventions

Firmware lives in `firmware/`, with board-specific timer/GPIO code in `firmware/src/boards/`. Python lives in `src/camsync_check/`, packaged profiles alongside it, and run examples in `configs/`. `data/`, `outputs/`, `.venv/`, and build caches are ignored.

All repository text and commits use English. Keep usage here, development rules in [AGENTS.md](AGENTS.md), and rationale in `docs/design.md`. Comprehensive automated tests are required: unit, integration, deterministic synthetic-image, and end-to-end CLI coverage, including the two-board workflow and failure cases. Run affected tests during development and the full suite before completing implementation changes. Software tests do not establish physical timing accuracy. Request missing dependencies before installation. The repository retains its [GPL v3 license text](LICENSE).

Run the current automated suite with `make test` (standard-library `unittest`, using `.venv`). Upload tests use a fake Arduino CLI and never access a real board. Current coverage is limited to the host upload/monitor wrapper and its Make integration; image-analysis, protocol, and firmware behavior tests remain to be implemented. No real upload has been validated yet.
