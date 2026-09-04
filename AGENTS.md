# Contributor and Agent Instructions

## Project scope

- Read `README.md` and `docs/design.md`. This small scientific tool contains MCU firmware and offline image analysis, not camera acquisition.
- Write all repository documentation, code, comments, configuration descriptions, and commit messages in English. Conversation follows the user's language.
- Keep usage and configuration guidance in README, development rules here, and measurement rationale in `docs/design.md`. Update these instead of adding overlapping documents or empty-directory READMEs.
- Implement only needed behavior. Do not add unsolicited fallbacks, automatic degradation, speculative plugin systems, compatibility layers, or complex configuration inheritance.
- Commit small, complete changes frequently. Do not push automatically, rewrite history, overwrite user edits, or include unrelated changes.

## Environment and execution

- Build firmware only in the shared `.devcontainer/` environment; use the root Makefile from the host. Flashing is separate from compilation. Normally program RA4M1 only and retain official ESP32-S3 firmware.
- Use only the project `.venv/bin/python` for Python work and `.venv/bin/python -m pip` for package operations. Do not search conda or other environments. If `.venv` is missing, request authorization before bootstrapping it with a system interpreter; do not silently fall back to system Python.
- Request missing dependency installation rather than installing automatically or substituting another implementation. Container dependency declarations are not evidence of a successful build.
- Do not write or run tests, local smoke checks, simulations, or benchmarks without an explicit user request. Document/diff review and declarative configuration inspection are permitted.
- Provide granular stderr progress for long image-processing operations. Keep machine-readable results on stdout or in files; never log inside an MCU ISR.

## Implementation

- Keep GPIO, timers, and electrical mappings in `firmware/src/boards/<board_id>/`. Use hardware timers and bounded, precomputed ISR work; no delays, serial output, dynamic allocation, or blocking operations in the critical path.
- Never run the official matrix scanner alongside the custom driver. Preserve unrelated GPIO bits and establish safe high-impedance transitions, source/sink polarity, and duty cycles from hardware evidence.
- Keep analysis in `src/camsync_check/`, with thin CLI orchestration. Use explicit JSON run settings and complete profiles, including packaged built-ins and user-provided files. Never infer image dimensions, camera identity, or pixel format.
- Treat the MCU target and input camera as different profile kinds. Keep Python-package profiles and firmware board IDs consistent. Record resolved profiles in analysis outputs.
- Support two B0267 synchronization boards as separate sources, each with four camera views. Keep synchronization-board identity separate from acquisition-node identity; two boards may share one node. Do not assume the four views have zero optical skew or infer cross-board frame pairing from equal file indices.
- Prefer standard-library facilities; planned dependencies are NumPy, OpenCV headless, and tqdm. Add modules as functionality appears, not as empty abstractions.
- Use Python type annotations, four-space code indentation, explicit firmware integer widths, and time-unit suffixes. Make recipes use tabs.

## Measurement and data

- Separate slot duration, optical timing error, MCU clock-scale error, decoder uncertainty, and measured accuracy. Host timestamps and frame numbers are not optical ground truth.
- Preserve the offset and drift being measured. Report ambiguity, saturation, missing frames, unknown exposure, and unsupported shutter timing explicitly; never fill invalid results with zero offset.
- The first release uses thresholded contiguous LED intervals at 250 us slots, targeting 1 ms checks under an explicit less-than-10-ms cross-board offset assumption. Do not add brightness fitting or long-code decoding. Unknown exposure requires no substituted duration; derive only slot-level bounds and reject ambiguous LED patterns. Report the prior and conditional uncertainty, not calibrated accuracy.
- State the estimated exposure instant, valid coverage, rejection reasons, and uncertainty sources. Version configurations and protocols when their semantics change.
- Keep captures, private settings, and generated results out of Git. Add example images only with explicit authorization.
- Preserve upstream attribution and licensing; record source versions when importing hardware mappings or code.
