# Configuration and Results

## Run configuration

Start with `configs/example.json` for one B0267 or `configs/two-b0267.json` for two. Both contain fictional paths. Replace them with your ordered image list and meaningful cross-board frame pairs. All file references resolve relative to the run JSON; reference-image paths resolve relative to their own reference JSON.

| Section | Purpose |
| --- | --- |
| `schema_version` | Run schema version, currently 1 |
| `target` | `builtin:uno_r4_wifi`, protocol `r4-rowmajor96-v2`, slot 250 µs |
| `sources` | Ordered images, camera profile, camera IDs, synchronization-board ID, acquisition-node ID |
| `comparison` | Optional comparison between two sources, representative cameras, and explicit frame pairs |
| `localization` | Reference asset and number of source frames to inspect |
| `analysis` | Image thresholds, conditional timing bounds, and optional pass tolerance |
| `output` | Directory for a new analysis; existing result files are not overwritten |

Protocol v2 replaces `r4-permuted96-v1`. Update the firmware and run configuration together. The previous `orientation_margin` setting has been removed; orientation comes from the reference image. Image data alone does not authenticate firmware identity: inspect serial `?` before capture.

## Camera profiles and sources

`builtin:b0267` describes 5120 × 800, single-channel uint8, global shutter, and four horizontal 1280 × 800 crops. View order is not an inferred physical connector identity. Each source maps every profile view to a globally unique camera ID. Synchronization-board IDs are unique; node IDs may be shared by multiple boards.

A complete custom JSON profile can replace `builtin:b0267` with `./my-camera.json`:

```json
{
  "schema_version": 1,
  "kind": "camera",
  "model": "My global-shutter camera",
  "image": {"width": 1280, "height": 800, "channels": 1, "dtype": "uint8"},
  "shutter": "global",
  "views": [{"id": "full", "crop_xywh": [0, 0, 1280, 800]}]
}
```

Map that view with `"camera_ids": {"full": "camera_a"}`. Image dimensions, type, and crop boundaries are validated exactly. Rolling shutter, color images, resizing, automatic profile inference, and profile inheritance are not implemented.

Exposure metadata is recorded without constraining the decoder: `{"value_us": null, "provenance": "unknown"}` is valid. Other provenance values are `requested`, `reported`, and `calibrated`, paired with a positive value in microseconds. Exposure may vary between frames; no default duration is inserted. Optional source `frame_period_us` only scales drift to µs/second and is labeled as a configured time basis.

## Frame pairing and board comparisons

`comparison.frame_pairs` lists strictly increasing one-to-one pairs of zero-based indices into the two source image lists. These are the acquisition system's pairings to inspect; they are not inferred or adjusted to minimize offset. Unpaired indices are listed in the results, not diagnosed as dropped captures.

Each paired source image contributes up to 16 cross-board camera comparisons. Each source image also contributes six within-board pairs. The representative-camera summary uses exactly the configured cameras; a missing representative is never substituted. Node comparison means the optical offset between those cameras, not a host-clock measurement.

## Localization

```json
"localization": {
  "reference": "builtin:uno_r4_wifi",
  "max_frames": 8,
  "min_valid_frames": 2
}
```

The tool selects up to `max_frames` evenly distributed images from each source. SIFT matches stable PCB texture to the reference, including an explicitly reflected reference variant for mirrored images. RANSAC estimates the grid's perspective and numbering direction. Multiple successful source frames must agree before geometry is reused for the sequence.

Changing LED brightness then refines the predicted grid in original image coordinates. At least 12 changing LED positions with sufficient spatial spread are needed, not all 96. Repeated identical LED phases may provide no refinement evidence. The board and camera must remain stationary throughout capture; checking selected frames does not prove the absence of motion between them.

The R4-specific geometry checks currently require:

- At least 12 unique destination feature matches and 12 RANSAC inliers; inlier fraction at least 0.5 and reference feature coverage at least 0.05.
- Match distance ratio below 0.75 and RANSAC reprojection threshold 2 px. Maximum accepted inlier residual is the smaller of 3 px or 0.3 LED pitch.
- At least 6 px between neighboring LEDs. Reference estimates must agree within 0.3 pitch; conflicting mirrored/original hypotheses are rejected.
- Optical refinement from at least 12 changing LED centers spanning a convex-hull area of 8 grid cells, with residual at most 0.2 pitch and correction at most 0.3 pitch.

These are initial algorithm thresholds, not established capture-quality guarantees. Inspect the report's per-frame matching evidence, temporal projection, and numbered-grid overlays.

A custom `localization.reference` can name a JSON file with the same schema as the [built-in reference](../src/camsync_check/references/uno_r4_wifi.json). Provide a sharp reference image, explicit image size, `led_corners_xy` in physical LED order **0, 11, 95, 84**, a feature polygon, exclusion polygons, and provenance. This is board-template preparation, not per-camera calibration. See [reference maintenance](development.md#reference-maintenance).

## Measurement settings

| Field | Meaning |
| --- | --- |
| `on_threshold` | Foreground mean minus local-background median needed to count a LED as on; example 20 |
| `threshold_margin` | Reject a frame if any LED lies this close to the on threshold; example 5 |
| `max_saturated_fraction` | Reject when an on LED exceeds this fraction of foreground pixels at 255; example 0.25 |
| `boundary_slack_slots` | Allowed missed boundary slots per camera; example 1 |
| `max_abs_offset_us` | Independently established absolute offset prior; example 10000, strictly less than half the cycle |
| `target_resolution_us` | Maximum permitted conditional pair half-width; example 1000 |
| `pass_tolerance_us` | Optional absolute-offset acceptance limit; null means no pass/fail decision |

The default half-width is `(boundary_slack_slots + 1) * 250 = 500 µs`. It assumes correct geometry and slot classification; it is not a statistical confidence interval. Never increase the boundary allowance simply to conceal poor images. The [measurement design](design.md) explains the bounds and cycle ambiguity.

## Outputs and troubleshooting

| Artifact | Contents |
| --- | --- |
| `report.html` | Offline report, pair statistics, 4 × 4 matrix, and diagnostics |
| `frames.csv` | Per-view validity, first/last slots, start/end phase, exposure bounds, modulo phase step |
| `led_signals.csv` | Background-subtracted signals in physical row-major LED order |
| `pairs.csv` | Associations, signed offsets, conditional bounds, rejection reasons, optional decisions |
| `summary.json` | Median, jitter SD, P95 residual, range, drift, coverage, versions, limits |
| `resolved.json` | Run settings, resolved profiles, localization/reference snapshot |
| `localization.json` | Template provenance and hash, per-frame matching evidence, geometry, rejection reasons |
| `localization/`, `diagnostics/` | Temporal projections, numbered grids, and first-frame sampling overlays |

`reference_not_found` or `insufficient_reference_frames`: provide original-resolution frames, improve focus, show more stable board texture, or prepare a suitable custom reference. The earlier 596 × 390 user screenshot did not supply enough reliable matches to the built-in reference; it has not demonstrated real-capture localization success.

`moving_or_inconsistent_reference`: geometry or numbering disagrees between selected frames. Keep the target stationary and inspect the images. `insufficient_led_evidence`: too few LED positions changed, or they occupy too small a part of the grid. `invalid_led_geometry`: observed spots disagree with the reference; inspect clipping, blur, optical distortion, and template coordinates.

Other explicit rejections include threshold ambiguity, saturation, disconnected lit intervals, nearly full cycles, and offsets inconsistent with the prior. Invalid measurements stay empty/null, not zero. Unreadable files and malformed configuration terminate the command. Exit status 0 means processing completed; it is not a synchronization pass.
