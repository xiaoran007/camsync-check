# camsync-check

MCU-driven LED firmware and an offline Python tool for checking multi-camera exposure synchronization. Users supply images; camera acquisition stays outside this repository.

**Status:** engineering scaffold. Container definitions and configuration examples exist; firmware, configuration loading, image decoding, and the CLI are not implemented. No timing accuracy has been established.

## Firmware development

Use Docker with Compose and Make, or VS Code's **Reopen in Container** command. Both paths use the same `.devcontainer/compose.yaml` service and Dockerfile; host PlatformIO is not required.

```sh
make image                       # Build the firmware environment
make dev                         # Open a container shell
make firmware                    # Build the default board
make firmware BOARD=uno_r4_wifi   # Explicit PlatformIO environment
```

Inside the container, use `pio run -d firmware -e uno_r4_wifi`. Firmware builds always run in the container. There is no firmware entry point yet, so these build commands cannot produce a firmware image at this stage.

The initial environment uses Debian Bookworm, Linux amd64, PlatformIO Core 6.1.18, and `renesas-ra@1.9.0`. ARM hosts use emulation. First use downloads dependencies inside the container. Artifacts appear in `firmware/.pio/`; packages are cached in `.cache/platformio/`. The base-image tag and transitive dependencies are not fully locked; record resolved versions and image identity at the first authorized build.

Uploading is a separate operation on the resulting artifact. USB passthrough and flashing are not configured, and no host-side compilation path is provided. Implementation targets RA4M1 only, retaining the official ESP32-S3 firmware.

## Image analysis configuration

Python 3.11+ with NumPy, OpenCV headless, and tqdm. Use the repository's `.venv/bin/python` exclusively, including `.venv/bin/python -m pip` for package operations. Do not search conda or other environments; request authorization before using a system interpreter to create a missing `.venv`. The intended interface is:

```sh
camsync-check --config configs/example.json
```

This command is a planned interface, not an installed executable. The [single-board example](configs/example.json) and [two-board example](configs/two-b0267.json) use fictional image paths and unknown exposure.

Keep two explicit configuration layers:

- **Profiles** describe reusable hardware facts. Built-ins ship inside the Python package: `builtin:b0267` specifies 5120 × 800, single-channel uint8, global shutter, and four horizontal crops; `builtin:uno_r4_wifi` describes the LED target.
- **Run configuration** selects profiles, ordered image paths, camera/node identities, exposure information, target protocol, and output directory.

To use another camera or image layout, supply a complete JSON profile using the same camera schema and replace `"profile": "builtin:b0267"` with `"profile": "./my-camera.json"`. A standalone camera uses one view whose crop covers the whole image. Add sources for additional sequences or nodes. Source `camera_ids` must map every profile view to a globally unique camera ID; view order is not a physical connector identity.

For two B0267 boards, supply two wide-image sequences, each with its own `sync_board_id` and four camera IDs. `node_id` may be identical when both boards connect to one host. The draft `comparison` selects source IDs and representative cameras. Its explicit `frame_pairs` lists zero-based source-frame index pairs to inspect; the example pairs are illustrative, not an assertion of simultaneous exposure. A future optical-association mode will report inferred pairings separately. Compare representative cameras without silently switching to another camera, while retaining all visible-camera pair results and within-board skew diagnostics.

Profile names use the explicit `builtin:` prefix; other references are file paths. File references, image paths, and the output directory resolve against the run configuration's directory. No profile inheritance, deep merging, filename-based identity inference, automatic resizing, or inferred camera model is planned. Load image values unchanged and require exact configured dimensions, channel count, and dtype. Reject invalid fields, unknown profiles, invalid crops, mismatched view mappings, and unreadable files with their locations.

Exposure uses microseconds plus `requested`, `reported`, `calibrated`, or `unknown` provenance. `null` means unknown, never zero. Fixed exposure may be supplied per source; variable exposure requires future explicit per-frame metadata support. Unknown exposure may limit analysis to geometry or ambiguous timing results. Built-in B0267 settings do not assume a frame rate or exposure duration.

Resolved profiles and run settings must accompany results so the analysis remains traceable. See [measurement design](docs/design.md) for decoding, ambiguity, and reporting requirements.

## Repository layout and conventions

```text
.devcontainer/                    Shared firmware environment
Makefile                          Short host-side container commands
firmware/                         PlatformIO project and board-specific code
src/camsync_check/                Analysis library and future CLI
src/camsync_check/profiles/       Packaged camera and target profiles
configs/example.json             Example run configuration
docs/design.md                   Measurement design and primary references
data/, outputs/, .cache/         Local artifacts, ignored by Git
```

All repository text and commit messages use English. Keep usage/configuration instructions here, development rules in [AGENTS.md](AGENTS.md), and measurement rationale in `docs/design.md`; avoid additional overview documents, duplicate setup guides, and README files for empty directories.

Request missing dependencies before installation. Do not run scientific tests, smoke checks, or experiments unless explicitly requested.

The repository retains its [GPL v3 license text](LICENSE).
