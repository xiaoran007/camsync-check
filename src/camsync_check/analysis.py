"""Pairwise timing under an explicit offset prior; no exposure fitting."""

from collections import Counter
from itertools import combinations
import csv
from pathlib import Path

import numpy as np
from tqdm import tqdm

from .config import Run
from .localize import localize
from .report import save_json
from .vision import camera_view, decode, read_frame, sample, write_overlay


FRAME_FIELDS = ["source_id", "sync_board_id", "node_id", "frame_index", "image", "camera_id",
                "status", "reason", "first_slot", "last_slot", "lit_count", "phase_start_us",
                "phase_end_us", "exposure_min_us", "exposure_max_us", "phase_step_us"]
PAIR_FIELDS = ["kind", "reference_source", "other_source", "reference_camera", "other_camera",
               "reference_frame", "other_frame", "representative", "status", "reason", "offset_us",
               "lower_us", "upper_us", "cycle_shift", "decision"]


def compare(left: dict, right: dict, run: Run) -> dict:
    result = {"status": "invalid", "reason": "", "offset_us": None, "lower_us": None,
              "upper_us": None, "cycle_shift": None, "decision": "inconclusive"}
    if left["status"] != "valid" or right["status"] != "valid":
        result["reason"] = f"reference:{left['reason'] or 'valid'};other:{right['reason'] or 'valid'}"
        return result
    period = run.slot_us * run.led_count
    radius = (run.settings.boundary_slack + 1) * run.slot_us
    difference = right["phase_start_us"] - left["phase_start_us"]
    limit = run.settings.max_offset_us
    candidates = [(difference + k * period, k) for k in range(-2, 3)
                  if difference + k * period - radius < limit
                  and difference + k * period + radius > -limit]
    if len(candidates) != 1:
        result["reason"] = "ambiguous_cycle" if candidates else "offset_prior_not_satisfied"
        return result
    offset, shift = candidates[0]
    low, high = offset - radius, offset + radius
    result.update(offset_us=offset, lower_us=low, upper_us=high, cycle_shift=shift)
    # Do not clip intervals at the prior and manufacture precision there.
    if low < -limit or high > limit:
        result["reason"] = "offset_prior_boundary"
        return result
    result.update(status="valid", reason="", decision="not_requested")
    tolerance = run.settings.pass_tolerance_us
    if tolerance is not None:
        if low >= -tolerance and high <= tolerance:
            result["decision"] = "pass"
        elif high < -tolerance or low > tolerance:
            result["decision"] = "fail"
        else:
            result["decision"] = "inconclusive"
    return result


def statistics(rows: list[dict], frame_period_us: float | None = None) -> dict:
    valid = [row for row in rows if row["status"] == "valid"]
    result = {"total_pairs": len(rows), "valid_pairs": len(valid),
              "valid_fraction": len(valid) / len(rows) if rows else 0,
              "rejection_counts": dict(Counter(row["reason"] for row in rows if row["status"] != "valid")),
              "median_offset_us": None, "observed_jitter_std_us": None,
              "p95_absolute_residual_us": None, "peak_to_peak_us": None,
              "drift_us_per_reference_frame": None, "drift_us_per_second": None,
              "drift_time_basis": "configured_frame_period" if frame_period_us else None}
    if not valid:
        return result
    values = np.array([row["offset_us"] for row in valid], dtype=float)
    median = float(np.median(values))
    result.update(median_offset_us=median,
                  observed_jitter_std_us=float(np.std(values, ddof=1)) if len(values) > 1 else None,
                  p95_absolute_residual_us=float(np.percentile(np.abs(values - median), 95)),
                  peak_to_peak_us=float(np.ptp(values)))
    x = np.array([row["reference_frame"] for row in valid], dtype=float)
    if len(x) >= 3 and np.ptp(x) > 0:
        centered = x - x.mean()
        slope = float(np.dot(centered, values - values.mean()) / np.dot(centered, centered))
        result["drift_us_per_reference_frame"] = slope
        if frame_period_us is not None:
            result["drift_us_per_second"] = slope * 1e6 / frame_period_us
    return result


def analyze(run: Run) -> tuple[list[dict], dict]:
    run.output.mkdir(parents=True, exist_ok=True)
    outputs = ["frames.csv", "led_signals.csv", "pairs.csv", "summary.json", "report.html", "resolved.json", "localization.json"]
    if any((run.output / name).exists() for name in outputs):
        raise ValueError(f"Analysis outputs already exist in {run.output}; choose a new output directory")
    localization, sampling = localize(run)
    save_json(run.output / "localization.json", localization)
    run.snapshot["localization"] = localization
    order = np.array(run.scan_order)
    diagnostics = run.output / "diagnostics"
    diagnostics.mkdir(exist_ok=True)
    observations = {}
    previous = {}
    frame_rejections = Counter()
    total_frames = sum(len(s.frames) for s in run.sources)
    with ((run.output / "frames.csv").open("w", newline="", encoding="utf-8") as frame_file,
          (run.output / "led_signals.csv").open("w", newline="", encoding="utf-8") as signal_file,
          tqdm(total=total_frames, desc="Decode source images", unit="image") as progress):
        frame_writer = csv.DictWriter(frame_file, fieldnames=FRAME_FIELDS)
        frame_writer.writeheader()
        signal_writer = csv.writer(signal_file)
        signal_writer.writerow(["source_id", "frame_index", "camera_id"] + [f"led_{i}" for i in range(96)])
        for source in run.sources:
            for index, path in enumerate(source.frames):
                frame = read_frame(path, source)
                for camera in source.cameras:
                    identity = {"source_id": source.id, "sync_board_id": source.board_id,
                                "node_id": source.node_id, "frame_index": index, "image": str(path),
                                "camera_id": camera.id}
                    geometry = sampling[camera.id]
                    if geometry is None:
                        observation = {"status": "invalid", "reason": "localization_failed:" + localization["cameras"][camera.id]["reason"]}
                    else:
                        view = camera_view(frame, camera)
                        signals, saturation = sample(view, geometry)
                        observation = decode(signals[order], saturation[order], run.settings, run.slot_us)
                        signal_writer.writerow([source.id, index, camera.id] + signals.tolist())
                        # One review image per camera; all frame measurements remain in CSV.
                        if index == 0:
                            write_overlay(diagnostics / f"{camera.id}.png", view, geometry, signals,
                                          run.settings, observation["reason"])
                    row = identity | observation
                    row["phase_step_us"] = None
                    old = previous.get(camera.id)
                    if observation["status"] == "valid":
                        if old is not None:
                            period = run.slot_us * run.led_count
                            row["phase_step_us"] = (observation["phase_start_us"] - old + period / 2) % period - period / 2
                        previous[camera.id] = observation["phase_start_us"]
                    else:
                        previous[camera.id] = None
                        frame_rejections[observation["reason"]] += 1
                    frame_writer.writerow(row)
                    observations[(source.id, index, camera.id)] = observation
                progress.update(1)
    pairs = []

    def add_pair(kind: str, left_source, right_source, left_camera: str, right_camera: str,
                 left_index: int, right_index: int, representative: bool = False) -> None:
        measurement = compare(observations[(left_source.id, left_index, left_camera)],
                              observations[(right_source.id, right_index, right_camera)], run)
        pairs.append({"kind": kind, "reference_source": left_source.id, "other_source": right_source.id,
                      "reference_camera": left_camera, "other_camera": right_camera,
                      "reference_frame": left_index, "other_frame": right_index,
                      "representative": representative} | measurement)

    for source in run.sources:
        for index in tqdm(range(len(source.frames)), desc=f"Within-board {source.id}", unit="frame"):
            for a, b in combinations(source.cameras, 2):
                add_pair("within_board", source, source, a.id, b.id, index, index)
    unmatched = {}
    if run.comparison is not None:
        c = run.comparison
        sources = {source.id: source for source in run.sources}
        left_source, right_source = sources[c.reference], sources[c.other]
        for n, m in tqdm(c.pairs, desc="Cross-board pairs", unit="pair"):
            for a in left_source.cameras:
                for b in right_source.cameras:
                    add_pair("cross_board", left_source, right_source, a.id, b.id, n, m,
                             a.id == c.reference_camera and b.id == c.other_camera)
        unmatched = {
            c.reference: sorted(set(range(len(left_source.frames))) - {n for n, _ in c.pairs}),
            c.other: sorted(set(range(len(right_source.frames))) - {m for _, m in c.pairs})}
    with (run.output / "pairs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerows(pairs)
    lookup = {source.id: source for source in run.sources}
    groups = {}
    for row in pairs:
        key = (row["kind"], row["reference_source"], row["other_source"],
               row["reference_camera"], row["other_camera"])
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, rows in groups.items():
        kind, source_a, source_b, camera_a, camera_b = key
        summaries.append({"kind": kind, "reference_source": source_a, "other_source": source_b,
                          "reference_camera": camera_a, "other_camera": camera_b}
                         | statistics(rows, lookup[source_a].frame_period_us))
    primary = [row for row in pairs if row["representative"]]
    primary_period = lookup[run.comparison.reference].frame_period_us if run.comparison else None
    summary = {"schema_version": 1, "protocol": "r4-permuted96-v1", "metric": "exposure_start_offset",
               "units": "us", "slot_us": run.slot_us, "period_us": run.slot_us * run.led_count,
               "max_abs_offset_prior_us": run.settings.max_offset_us,
               "target_resolution_us": run.settings.resolution_us,
               "conditional_pair_half_width_us": (run.settings.boundary_slack + 1) * run.slot_us,
               "boundary_slack_slots_per_camera": run.settings.boundary_slack,
               "hardware_accuracy_validated": False,
               "pairing": "user_supplied_only", "unmatched_source_frames": unmatched,
               "frame_rejection_counts": dict(frame_rejections),
               "representative_pair": statistics(primary, primary_period), "camera_pairs": summaries,
               "pass_tolerance_us": run.settings.pass_tolerance_us,
               "pair_decision_counts": dict(Counter(row["decision"] for row in primary)),
               "limitations": [
                   "Cycle choice assumes each reported pair differs by less than the configured prior; this is not independently verified.",
                   "Slot bounds assume correct geometry, contiguous exposure, no spurious lit LEDs, and no more missed boundary LEDs than configured.",
                   "Exposure must span less than one sweep; disconnected, near-full, saturated, and threshold-ambiguous observations are rejected.",
                   "Phase steps are modulo the sweep period, not absolute frame intervals or evidence of missing frames.",
                   "Observed jitter includes quantization and image decoding error. No global synchronization pass is inferred from partial coverage."]}
    return pairs, summary
