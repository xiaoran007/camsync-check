# Contributor and Agent Instructions

## Scope and working conventions

- This is scientific measurement software comprising MCU firmware and offline CV analysis. Read `docs/design.md`, `docs/protocol.md`, and relevant hardware notes before implementation.
- All repository documentation, code comments, identifiers, configuration descriptions, and commit messages must be in English. Conversation language follows the user.
- Users own camera acquisition. Accept images and descriptive metadata; do not integrate camera drivers, SDKs, acquisition programs, or runtime dependencies on another acquisition repository.
- Keep implementations simple. Do not add unsolicited fallback logic, automatic degradation, compatibility layers, or features.
- Do not write or run tests, local smoke checks, simulations, or benchmarks unless explicitly requested by the user. Document review and Git diff inspection are permitted.
- If a required dependency is missing, request installation of the specific dependency instead of installing it automatically or substituting a different implementation.
- Long image processing operations should expose granular progress on stderr. Machine-readable results belong on stdout or in files. Never log or render progress inside an MCU ISR.
- Commit small, complete changes frequently. Do not mix unrelated changes, push automatically, overwrite user edits, or rewrite history without authorization.

## Python

- Before using Python, check project `.venv` / `venv` environments first, then available conda environments.
- Record the selected interpreter's absolute path and use its associated package installation tools.
- Always obtain user authorization before using system Python. Do not bypass this rule through script shebangs or wrappers.
- Use a `src/camsync_check/` package. Keep CLI argument handling and orchestration separate from analysis.
- The initial target is Python 3.11+. Planned minimal runtime dependencies are NumPy, OpenCV headless, and tqdm; follow `docs/development.md` for installation and version management.

## Firmware

- Normally program only RA4M1, retaining the official ESP32-S3 firmware. Use VS Code / PlatformIO; do not require Arduino IDE.
- Build firmware only in the shared Dev Container environment. Use the root Makefile from the host; do not introduce a second native build path. Flashing is a separate hardware operation.
- Keep board-specific GPIO, timer, and pin mappings under `firmware/src/boards/<board_id>/`.
- Use hardware timers as the timing basis. ISR work must be bounded and precomputed where possible; no delays, serial output, dynamic allocation, or blocking operations.
- Never run the official matrix scanner alongside the custom driver. Modify only matrix-related GPIO bits and preserve other peripherals.
- Justify high-impedance transitions, source/sink switching, and duty cycles using hardware evidence. Do not extrapolate scan-mode electrical conditions to continuous illumination.
- Record upstream versions and mapping orientation. Preserve license notices and attribution when importing third-party code.

## Measurement and data

- Distinguish slot duration, optical edge error, MCU clock scale error, decoder uncertainty, and observed measurement accuracy.
- Frame indices and host timestamps are not shared exposure ground truth. Alignment must not remove the offset or drift being measured.
- Report periodic ambiguity, insufficient exposure information, saturation, occlusion, missing frames, and unmodeled rolling shutter explicitly; never substitute a plausible zero offset.
- Keep raw captures, private experiment settings, and generated reports out of Git. Only include anonymized example data explicitly authorized for inclusion.
- Version optical protocols, board profiles, and report formats separately. Update documentation whenever decoding semantics change.
- State which exposure instant is estimated, the valid coverage, rejection reasons, and uncertainty sources in every report.
