# Contributor and Agent Instructions

## Project scope

- Read `README.md` and `docs/design.md`. This small scientific tool contains MCU firmware and offline image analysis, not camera acquisition.
- Write all repository documentation, code, comments, configuration descriptions, and commit messages in English. Conversation follows the user's language.
- Keep README user-first: purpose, capture requirements, quick start, and links. Keep detailed run/reference configuration in `docs/configuration.md`, build/test/maintenance instructions in `docs/development.md`, and measurement rationale in `docs/design.md`. Keep contributor rules here. Avoid duplicated guidance and empty-directory READMEs.
- Implement only needed behavior. Do not add unsolicited fallbacks, automatic degradation, speculative plugin systems, compatibility layers, or complex configuration inheritance.
- Commit small, complete changes frequently. Do not push automatically, rewrite history, overwrite user edits, or include unrelated changes.

## Environment and execution

- Build firmware only in the shared `.devcontainer/` environment; use the root Makefile from the host. Flashing is separate from compilation. Normally program RA4M1 only and retain official ESP32-S3 firmware.
- Use only the project `.venv/bin/python` for Python work and `.venv/bin/python -m pip` for package operations. Do not search conda or other environments. If `.venv` is missing, request authorization before bootstrapping it with a system interpreter; do not silently fall back to system Python.
- Request missing dependency installation rather than installing automatically or substituting another implementation. Container dependency declarations are not evidence of a successful build.
- Comprehensive automated tests are required for this project. Writing and running tests, including deterministic synthetic-image checks, is part of normal implementation and maintenance and requires no separate request. This project-specific rule supersedes the earlier restriction on scientific-code tests.
- Provide granular stderr progress for long image-processing operations. Keep machine-readable results on stdout or in files; never log inside an MCU ISR.

## Implementation

- Keep GPIO, timers, and electrical mappings in `firmware/src/boards/<board_id>/`. Use hardware timers and bounded, precomputed ISR work; no delays, serial output, dynamic allocation, or blocking operations in the critical path.
- Never run the official matrix scanner alongside the custom driver. Preserve unrelated GPIO bits and establish safe high-impedance transitions, source/sink polarity, and duty cycles from hardware evidence.
- Keep analysis in `src/camsync_check/`, with thin CLI orchestration. Use explicit JSON run settings and complete profiles, including packaged built-ins and user-provided files. Never infer image dimensions, camera identity, or pixel format.
- Treat the MCU target and input camera as different profile kinds. Keep Python-package profiles and firmware board IDs consistent. Record resolved profiles in analysis outputs.
- Support two B0267 synchronization boards as separate sources, each with four camera views. Keep synchronization-board identity separate from acquisition-node identity; two boards may share one node. Do not assume the four views have zero optical skew or infer cross-board frame pairing from equal file indices.
- Prefer standard-library facilities; runtime dependencies are NumPy, OpenCV headless, and tqdm. Add modules as functionality appears, not as empty abstractions.
- Use Python type annotations, four-space code indentation, explicit firmware integer widths, and time-unit suffixes. Make recipes use tabs.

## Testing

- Keep automated tests in `tests/`. Cover public behavior with unit, integration, and end-to-end CLI tests; include successful measurements, boundary cases, and explicit rejection paths. Add regression tests for bug fixes and update tests whenever behavior changes.
- Cover configuration validation, built-in and custom profiles, image dimensions and crops, automatic R4 localization and orientation, LED sampling, circular interval decoding, exposure bounds, cycle ambiguity, offset bounds, and pass/fail/inconclusive decisions.
- Exercise the complete two-B0267 workflow: eight independent views, within-board pairs, all 16 cross-board pairs, representative cameras, shared and separate node identities, explicit frame pairing, invalid or missing observations, statistics, and CSV/JSON/HTML outputs.
- Use deterministic synthetic fixtures with known geometry and exposure timing to check expected results independently of production decoding. Include rotation, reflection, perspective, incomplete phase coverage, saturation, noise, and ambiguous signals. Do not rely only on tests that reproduce the implementation or snapshots without behavioral assertions.
- Cover the shared firmware/decoder protocol and firmware state transitions where host-side checks are possible. Build firmware and run any C/C++ tests in the shared container. Python tests use the project `.venv`; request any missing test dependencies under the existing installation rule.
- Run affected tests during development and the full automated suite before declaring an implementation complete. Report commands, results, and remaining coverage gaps. Coverage metrics support review; they do not replace meaningful assertions.
- Keep software correctness separate from physical validation. Synthetic tests and successful builds cannot establish optical accuracy, electrical safety, ISR latency, or oscillator calibration. Hardware-dependent checks must be identified explicitly; unavailable hardware is not a passing result.

## Measurement and data

- Separate slot duration, optical timing error, MCU clock-scale error, decoder uncertainty, and measured accuracy. Host timestamps and frame numbers are not optical ground truth.
- Preserve the offset and drift being measured. Report ambiguity, saturation, missing frames, unknown exposure, and unsupported shutter timing explicitly; never fill invalid results with zero offset.
- The current protocol uses row-major LEDs 0 through 95 at 250 us slots, targeting 1 ms checks under an explicit less-than-10-ms offset assumption. Reference-image SIFT matching establishes geometric orientation independently of the optical sequence; the sequence repeats every 24 ms. Share the lookup table between firmware and decoder. Do not add brightness fitting or long-code decoding. Unknown exposure requires no substituted duration; reject ambiguous patterns and report conditional bounds, not calibrated accuracy.
- State the estimated exposure instant, valid coverage, rejection reasons, and uncertainty sources. Version configurations and protocols when their semantics change.
- Keep captures, private settings, and generated results out of Git. Deterministic synthetic fixture generators and small necessary test fixtures may be committed; real captures and unrelated example images still require explicit authorization.
- Preserve upstream attribution and licensing; record source versions when importing hardware mappings or code.
