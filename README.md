# camsync-check

Check multi-camera synchronization using an Arduino UNO R4 WiFi as a shared optical clock. The board flashes its built-in LEDs; the command-line tool reads saved images and reports camera offsets, jitter, and frame-level consistency.

Supports two Arducam B0267 synchronization boards with four cameras each, including boards on different acquisition nodes. Camera acquisition stays in your own software. LED localization is automatic, using a packaged R4 reference image and OpenCV; no model training or per-camera ROI annotation is required.

**Status:** firmware builds and automated software tests pass. Real-capture localization and 1 ms physical accuracy remain under validation. The target is approximately 1 ms checks, assuming you have independently established that paired exposures differ by less than 10 ms.

## What to capture

- Keep the R4 and cameras stationary. Every camera you want to compare must see the same board, including its printed features and complete LED matrix.
- Record a few seconds of ordered, original-resolution grayscale images. The current CLI accepts image sequences, not video files; preserve original frames when extracting video.
- Keep LEDs sharp and separated, without clipped highlights. Unknown exposure is supported; exposures must be shorter than the 24 ms LED cycle.
- Preserve your acquisition system's cross-board frame associations. The checker does not assume that both sequences' first frames correspond.

The built-in B0267 profile expects **5120 × 800 uint8 grayscale frames**, with four horizontal camera views. Other layouts use explicit profiles.

## Quick start

Use Docker with Compose, Make, and a project Python 3.11+ `.venv`. See [development setup](docs/development.md) for first-time environment and Arduino CLI installation.

```sh
make firmware                              # Compile in Docker
make ports                                 # Find the USB-connected R4 on the host
make upload PORT=/dev/cu.usbmodemXXXX        # Upload; replace the example port
make monitor PORT=/dev/cu.usbmodemXXXX       # Enter ? to inspect firmware status
```

Confirm `ready: true`, `mode: "sweep"`, and **`protocol: "r4-rowmajor96-v2"`**. The LEDs advance left-to-right, top-to-bottom at 250 µs per LED. Type `s` to select measurement mode; `c` shows corner diagnostics and `d` turns the matrix off. Exit the monitor with Ctrl-C.

**Upgrading from v1:** rebuild and reflash. The old scattered LED sequence is incompatible with v2 analysis. Use the updated example configurations and make new captures; this version rejects old protocol configurations.

Copy [the two-board configuration](configs/two-b0267.json), replace its fictional image paths and frame pairs, then run:

```sh
.venv/bin/python -m pip install -e .
.venv/bin/camsync-check --config configs/two-b0267.json
```

Open `report.html` in the configured output directory. It includes the representative-camera offset, jitter, the 4 × 4 cross-board comparison, within-board results, and localization diagnostics. Positive offset means the other camera exposes later. Failed measurements remain invalid, never zero. Choose a new output directory for each run.

The default conditional offset bound is ±500 µs. It is a model bound, not calibrated hardware accuracy. A completed command or partially valid report is not an overall synchronization pass.

## More information

- [Configuration and result files](docs/configuration.md): camera profiles, frame pairing, thresholds, references, and troubleshooting.
- [Development and setup](docs/development.md): environments, firmware commands, tests, and reference maintenance.
- [Measurement design](docs/design.md): timing bounds, assumptions, and hardware evidence.
- [Contributor rules](AGENTS.md).

Code uses [GPL v3](LICENSE). The packaged Arduino reference image retains its [upstream CC BY-SA 4.0 license](src/camsync_check/references/LICENSE-Arduino.txt) and attribution.
