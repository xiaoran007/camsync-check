# Optical Protocol and Data Contract

Status: draft. No decoder, parser, or firmware currently implements this contract. Version protocol semantics separately from application releases.

## Identifiers and units

- `board_id`: optical target model, initially `uno_r4_wifi`.
- `target_id`: physical LED board identity, distinct from camera aggregation-board identity.
- `protocol_id`: optical sequence definition, such as candidate `sweep96-v0`.
- `run_id`: one continuous target run; a reset starts a new run. This is not a shared host clock.
- `camera_id`, `node_id`, `source_id`: camera view, acquisition node, and source image sequence.
- `led_id = row * 12 + column`, zero-based; localization establishes physical orientation.
- Time field suffixes specify `_ticks`, `_us`, or `_ns`. Unknown values use `null`, never a fabricated zero.

## Planned firmware run description

Include firmware commit; board/profile/protocol versions and hashes; run ID; sequence parameters and period; timer type/channel/clock source/input frequency/divider/counts; nominal slot time; conduction and blanking windows; start/stop conditions; detected overruns; and calibration status.

ISR counts alone do not prove that hardware periods were not missed. Document overrun detection and its limitations. Preserve whether the microsecond scale was externally calibrated.

For v0, the global slot counter maps to `led_id = slot_index % 96`. When images establish only within-cycle time, output `phase_only` and the period; do not invent an epoch. v1 generation, optical start identification, and ambiguity requirements remain to be frozen in M3.

## User-provided image input

The planned CLI is `camsync-check analyze --input capture.json --output outputs/run-name`. This command is not implemented.

The manifest describes saved images and their grouping; it requires no camera SDK or acquisition service. The library should also accept already-loaded image arrays with equivalent metadata.

| Information | Contract |
| --- | --- |
| Format version, target model, protocol, slot parameters | Required for quantitative decoding; may come from the flashed firmware configuration without serial logs |
| `sources[].frames` | Ordered image paths; relative paths resolve against the manifest directory |
| `cameras[]` | Camera/node/source identifiers and optional crop; omitting crop uses the full image |
| `shutter` | `global`, `rolling`, or `unknown`; never default unknown input to global shutter |
| Exposure and provenance | May be unknown; distinguish requested, reported, and calibrated duration; per-frame values override constants |
| Host timestamps and driver frame IDs | Optional auxiliary metadata; include clock domain and semantics |
| Correspondences | Explicit capture groups can define pairings to inspect; matching file indices do not imply cross-node simultaneity |
| Geometry and brightness calibration | Required for quantitative fitting, potentially supplied in separate files |
| Acceptance criteria | Optional; without criteria, report measurements without pass/fail |

Use generic `crop_xywh` rectangles for composite frames, without a B0267-specific driver. Preserve source frame IDs and view identities. Views within one source image can form a group whose internal optical alignment is evaluated.

Unordered images support single-frame results, not continuous jitter or drift. Isolated images and images without exposure metadata can enter analysis, but may produce only observed LED positions, phase candidates, feasible intervals, or rejection reasons. Arbitrary image batches do not guarantee a unique complete timeline.

## Planned outputs

- `frames.csv`: camera/source/frame IDs, estimate type, exposure start/midpoint, feasible lower/upper bounds, exposure and provenance, phase/epoch status, quality, and rejection reasons.
- `pairs.csv`: camera pairs, associated frame IDs, association method, delta, uncertainty/intervals, and unmatched states. Preserve supplied and inferred pairings separately.
- `summary.json`: versions, configuration/data identity, camera/node statistics, sample counts, coverage, rejection counts, criteria, decisions, and limitations.
- `report.html`: an offline-readable report with per-frame offset curves, a pairwise offset matrix, coverage, diagnostic images, and method notes. CSV/JSON retain machine-readable values.

Call bounds feasible intervals unless a statistical model and coverage evidence justify confidence intervals. Shared reference errors can be correlated across cameras; do not automatically combine them as independent errors.

Never fill failed measurements with 0 µs. Candidate reason codes include `target_not_visible`, `saturated`, `insufficient_signal`, `ambiguous_epoch`, `unknown_exposure`, `unsupported_shutter`, and `unmatched_frame`. Invalid observations remain explicit measurement outputs; invalid configuration or unreadable files terminate the task with a precise location.
