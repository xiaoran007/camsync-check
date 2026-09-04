# Development Workflow

## Initialization status

This phase establishes documentation, Python package metadata, PlatformIO configuration, and directory scaffolding. No dependencies have been installed, Python executed, firmware built, tests or smoke checks run, or hardware flashed. There is no executable CLI or firmware yet.

## Language

All repository documentation, code comments, configuration descriptions, and commit messages are written in English. User-facing conversation may use the user's preferred language.

## Environments and dependencies

Target Python 3.11+. Check project `.venv` / `venv` first, then conda environments, and record the selected interpreter's absolute path. System Python requires explicit user authorization. Request missing dependency installation rather than downloading tools or creating environments implicitly.

`pyproject.toml` declares NumPy, OpenCV headless, and tqdm. Use standard-library argparse for the CLI. Dependency ranges are provisional; there is no validated lockfile. At the first authorized environment setup, resolve and record exact package versions, Python, and OS, then adopt a lockfile. Do not manufacture an unresolved lockfile or claim full reproducibility now.

The PlatformIO project lives in `firmware/`, initially using `renesas-ra@1.9.0`. Open that directory as the PlatformIO project in VS Code. There is no `main.cpp` yet; do not add empty `setup()` / `loop()` functions to suggest functional firmware exists.

At the first authorized build, record PlatformIO Core, framework, FSP, compiler, and board versions. A pinned platform does not pin every transitive package. Once firmware exists, the intended build command is `pio run -d firmware -e uno_r4_wifi`; uploading additionally uses `-t upload`. These commands have not been executed during initialization.

## Code organization

- `firmware/src/boards/uno_r4_wifi/`: source/sink mapping, timer configuration, and board operations.
- `firmware/src/`: entry point and board-independent sequencing, added as implemented.
- `firmware/include/`: genuinely shared headers.
- `src/camsync_check/`: analysis library; add modules with actual functionality, keeping CLI orchestration separate.
- `profiles/boards/`: geometry, LED indexing, and optical capabilities. Electrical mappings remain in firmware; both sides share board/profile identifiers.
- `examples/`: portable image descriptions without private paths or acquisition dependencies.
- `docs/`: design, protocol, evidence, and decisions.

Use type annotations and four-space indentation in Python. Use four spaces, explicit integer widths, and unit suffixes in C++. Abstract common board behavior only after multiple implementations demonstrate the need; do not build a speculative plugin framework.

## Changes and evidence

Commit small, complete changes with English messages, using prefixes such as `docs:`, `chore:`, `feat:`, and `fix:`. Report the change, evidence consulted, checks performed, and unverified behavior. Do not push automatically.

Do not write or execute scientific tests, smoke checks, simulations, or benchmarks without an explicit request. Document consistency and Git diff review are appropriate during initialization. Do not introduce a test framework, pre-commit hooks, or experimental CI automatically.

Store captures in ignored `data/` and results in ignored `outputs/`. Do not commit private images, machine addresses, credentials, or personal paths. Examples use fictional paths and public hardware identities.

Retain the existing LICENSE. Check licenses and preserve attribution when importing upstream code, including Arduino mappings or drivers.
