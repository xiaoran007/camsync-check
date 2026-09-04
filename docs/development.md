# Development Workflow

## Initialization status

This phase establishes documentation, Python package metadata, PlatformIO configuration, and directory scaffolding. No dependencies have been installed, Python executed, firmware built, tests or smoke checks run, or hardware flashed. There is no executable CLI or firmware yet.

## Language

All repository documentation, code comments, configuration descriptions, and commit messages are written in English. User-facing conversation may use the user's preferred language.

## Environments and dependencies

Target Python 3.11+. Check project `.venv` / `venv` first, then conda environments, and record the selected interpreter's absolute path. System Python requires explicit user authorization. Request missing dependency installation rather than downloading tools or creating environments implicitly.

`pyproject.toml` declares NumPy, OpenCV headless, and tqdm. Use standard-library argparse for the CLI. Dependency ranges are provisional; there is no validated lockfile. At the first authorized environment setup, resolve and record exact package versions, Python, and OS, then adopt a lockfile. Do not manufacture an unresolved lockfile or claim full reproducibility now.

Firmware builds run in the Dev Container defined by `.devcontainer/`. VS Code and Make share its Compose service, Dockerfile, workspace mount, and PlatformIO cache. The environment uses Linux amd64 (emulated on ARM hosts), Debian Bookworm, and PlatformIO Core 6.1.18. Run `make image` to build the environment, `make dev` for a container shell, and `make firmware` to compile. Docker with Compose is the only command-line container prerequisite; no separate Dev Container CLI is required.

The PlatformIO project lives in `firmware/`, initially using `renesas-ra@1.9.0`. There is no `main.cpp` yet, so the build entry point cannot produce firmware. Dependencies download inside the container on first use. Build artifacts remain under `firmware/.pio/`, with PlatformIO packages under `.cache/platformio/`. At the first authorized build, record resolved framework, FSP, compiler, and image identity; tags and dependency ranges do not establish a bit-for-bit reproducible build. Uploading is a separate hardware task; the build container does not expose USB or rebuild on the host. These build commands have not been executed.

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
