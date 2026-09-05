# Development and Setup

## Python environment

Use Python 3.11+ in the repository `.venv`. Agents must obtain authorization before using a system interpreter to create a missing environment and before installing missing dependencies; see [AGENTS.md](../AGENTS.md).

```sh
python3 -m venv .venv                 # One-time bootstrap with your approved interpreter
.venv/bin/python -m pip install -e .
```

All subsequent Python work uses `.venv/bin/python`. Runtime dependencies are NumPy, OpenCV headless, and tqdm. SIFT requires no model downloads or extra training dependencies. Do not search conda or silently substitute another interpreter.

## Firmware environment

Use Docker with Compose and Make, or VS Code's **Reopen in Container** command. Both use `.devcontainer/compose.yaml` and the same Dockerfile.

```sh
make image
make dev
make firmware
```

Inside the container, the equivalent build is `pio run -d firmware -e uno_r4_wifi`. Builds always run in the container. The environment pins the Debian Bookworm base image by digest, PlatformIO Core 6.1.18, `renesas-ra@1.9.0`, and ArduinoCore-renesas 1.6.0. Linux amd64 is used, with emulation on ARM hosts. The completed build used GCC 7.2.1. Transitive dependencies are not exhaustively locked.

Firmware products are in `firmware/.pio/build/uno_r4_wifi/`; packages are cached in `.cache/platformio/`. `firmware/generate_protocol.py` generates the C++ protocol header from the packaged target profile and rejects any table other than LEDs 0 through 95 for v2. Do not alter the table without changing protocol semantics and tests.

## Host upload and serial monitor

The host Arduino CLI handles USB; container passthrough is not needed. On macOS, with installation authorized:

```sh
brew install arduino-cli
arduino-cli core update-index
arduino-cli core install arduino:renesas_uno@1.6.0
```

```sh
make ports
make upload PORT=/dev/cu.usbmodemXXXX
make monitor PORT=/dev/cu.usbmodemXXXX
```

Replace the example port with the reported device. Set `ARDUINO_CLI=/path/to/arduino-cli` for an executable outside PATH. The wrapper uses `.venv` and only supports `BOARD=uno_r4_wifi`. It requires explicit ports, rejects missing/empty firmware, propagates errors, and never installs tools or retries automatically.

Upload writes the existing binary to RA4M1 and replaces its current application, retaining the ESP32-S3 bridge firmware. It does not rebuild; run `make firmware` after source changes. Close the monitor before uploading. If necessary, double-press RESET just after power-up, query ports again, and retry. See the [official board datasheet](https://docs-content.arduino.cc/resources/datasheets/ABX00087-datasheet.pdf) and [Arduino CLI upload reference](https://docs.arduino.cc/arduino-cli/commands-reference/arduino-cli_upload).

Serial uses 115200 baud. `?` reports protocol, timer clock, period counts, readiness, mode, and ISR count; `s` selects measurement, `c` corner diagnostics, and `d` dark. V2 status must identify `r4-rowmajor96-v2`. The firmware runs immediately after boot without waiting for serial. The user reported successful v1 flashing; v2 has been compiled but not flashed or physically validated by this implementation run.

## Tests

```sh
make test
make firmware
```

`make test` uses standard-library `unittest`; it requires no extra test framework. Coverage includes upload/monitor commands, protocol generation, configuration and custom profiles, SIFT localization, rotation/reflection/perspective, noise, partial LED visibility, timing bounds, invalid patterns, and full dual-B0267 CLI reports. End-to-end fixtures integrate known LED pulses into synthetic exposures independently of production decoding. Fake upload tools never access hardware.

Use affected tests while developing and run the complete suite before finishing a change. Regression tests accompany fixes. Remaining validation includes real captures across cameras/scenes, installed firmware behavior, ISR latency, electrical effects, and optical timing accuracy. Synthetic success and compiler success do not validate those properties. GPU inference, training, and benchmarking are not part of this implementation.

## Reference maintenance

The built-in image is Arduino's unmodified `featured.png` from `arduino/docs-content` commit `e0be49c2e6dfcf68923c3ddba166a982cea0c68a`. [Reference metadata](../src/camsync_check/references/uno_r4_wifi.json) records the source, creator, SHA-256, and license. The image and upstream license are packaged for offline use under CC BY-SA 4.0; code retains its repository license. The separate annotations were added by this project.

The canonical view has USB on the left, digital headers along the top, and the LED matrix at the lower right. Its LED centers 0, 11, 95, 84 are annotated in that order. Feature masks exclude the matrix, background, and major raised parts; avoid relying on cables, changing lights, or connector tops for planar geometry.

For another reference, photograph the same board revision sharply, preferably with the matrix dark and a near-front view. Annotate the four physical corner LED centers once, specify image dimensions, and select stable PCB texture. Preserve source and licensing information. Test transformed views and independent camera captures before distributing a revised reference. Neither template self-matching nor synthetic warping of the same image demonstrates cross-camera reliability. A custom template is an explicit configuration choice, not a silent fallback.

## Layout and documentation

- `firmware/`: PlatformIO project and board-specific timer/GPIO code.
- `src/camsync_check/`: offline analysis and thin CLI; profiles and reference assets ship inside the package.
- `scripts/board.py`: host upload/monitor orchestration.
- `tests/`: automated tests and deterministic fixture generators.
- `configs/`: user-editable run examples.

README is the user entry point. Detailed configuration belongs in `configuration.md`, development/setup here, and measurement reasoning in `design.md`. Keep contributor rules in root `AGENTS.md`. Captures, private settings, results, `.venv`, and caches stay out of Git. Use small English commits; do not push automatically.
