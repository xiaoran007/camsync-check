"""Automatic UNO R4 grid localization and permutation-based orientation."""

import cv2
import numpy as np
from tqdm import tqdm

from .config import ConfigError, Run
from .vision import Sampling, camera_view, decode, make_sampling, read_frame, sample, write_overlay


def detect_grid(projection: np.ndarray, camera, threshold: float) -> tuple[Sampling, float]:
    mask = np.uint8(projection >= threshold) * 255
    _, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # Tiny noise and large moving objects cannot be individual R4 LEDs.
    candidates = centroids[1:][(stats[1:, cv2.CC_STAT_AREA] >= 3)
                               & (stats[1:, cv2.CC_STAT_AREA] <= projection.size / 96)]
    if len(candidates) < 96:
        raise ConfigError(f"incomplete_grid: only {len(candidates)} candidate spots")
    found, points = cv2.findCirclesGrid(
        candidates.astype(np.float32).reshape(-1, 1, 2), (12, 8),
        flags=cv2.CALIB_CB_SYMMETRIC_GRID | cv2.CALIB_CB_CLUSTERING, blobDetector=None)
    if not found:
        raise ConfigError("grid_not_found: could not order a complete 12x8 grid")
    logical = np.float32([(x, y) for y in range(8) for x in range(12)])
    transform, _ = cv2.findHomography(logical, points.reshape(-1, 2), method=0)
    if transform is None:
        raise ConfigError("degenerate_grid: homography could not be fitted")
    fitted = cv2.perspectiveTransform(logical.reshape(1, -1, 2), transform)[0]
    pitch = float(np.linalg.norm(np.diff(fitted.reshape(8, 12, 2), axis=1), axis=2).min())
    residual = float(np.linalg.norm(fitted - points.reshape(-1, 2), axis=1).max())
    if not np.isfinite(fitted).all() or pitch <= 0 or residual > 0.2 * pitch:
        raise ConfigError("irregular_grid: homography residual exceeds 20% of LED pitch")
    return make_sampling(fitted[[0, 11, 95, 84]], camera), residual


def localize(run: Run) -> tuple[dict, dict[str, Sampling | None]]:
    directory = run.output / "localization"
    directory.mkdir(parents=True, exist_ok=True)
    result = {"schema_version": 1, "protocol": "r4-permuted96-v1", "cameras": {}}
    sampling = {}
    order = np.array(run.scan_order)
    base_indices = np.arange(96).reshape(8, 12)
    orientations = {"identity": base_indices.ravel(), "flip_rows": base_indices[::-1].ravel(),
                    "flip_columns": base_indices[:, ::-1].ravel(),
                    "rotate_180": base_indices[::-1, ::-1].ravel()}
    for source in run.sources:
        count = min(len(source.frames), run.localization.max_frames)
        indices = np.linspace(0, len(source.frames) - 1, count, dtype=int).tolist()
        maximum, minimum = None, None
        for index in tqdm(indices, desc=f"Locate {source.id}: temporal projection", unit="image"):
            frame = read_frame(source.frames[index], source)
            if maximum is None:
                maximum, minimum = frame.copy(), frame.copy()
            else:
                np.maximum(maximum, frame, out=maximum)
                np.minimum(minimum, frame, out=minimum)
        projection = maximum - minimum
        bases, samples = {}, {}
        for camera in tqdm(source.cameras, desc=f"Locate {source.id}: fit grids", unit="view"):
            cid = camera.id
            view = camera_view(projection, camera)
            entry = {"status": "invalid", "reason": "", "sampled_frame_indices": indices,
                     "view_size": list(camera.crop[2:])}
            result["cameras"][cid] = entry
            sampling[cid] = None
            if not cv2.imwrite(str(directory / f"{cid}-projection.png"), view):
                raise OSError(f"Could not write projection for {cid}")
            try:
                bases[cid], residual = detect_grid(view, camera, run.settings.threshold)
            except ConfigError as error:
                entry["reason"] = str(error)
                continue
            entry["max_grid_residual_px"] = residual
            samples[cid] = []
        if not bases:
            continue
        for index in tqdm(indices, desc=f"Locate {source.id}: identify orientation", unit="image"):
            frame = read_frame(source.frames[index], source)
            for camera in source.cameras:
                if camera.id in bases:
                    samples[camera.id].append(sample(camera_view(frame, camera), bases[camera.id]))
        for camera in source.cameras:
            cid = camera.id
            if cid not in bases:
                continue
            entry, base = result["cameras"][cid], bases[cid]
            scores = {}
            for name, permutation in orientations.items():
                score = 0
                for signals, saturation in samples[cid]:
                    decoded = decode(signals[permutation][order], saturation[permutation][order],
                                     run.settings, run.slot_us)
                    # A singleton or all-but-one pattern does not establish direction.
                    score += decoded["status"] == "valid" and 2 <= decoded["lit_count"] <= 94
                scores[name] = score
            ranked = sorted(scores, key=scores.get, reverse=True)
            entry["orientation_valid_frame_counts"] = scores
            best, second = ranked[:2]
            if (scores[best] < run.localization.min_valid_frames
                    or scores[best] - scores[second] < run.localization.orientation_margin):
                entry["reason"] = "orientation_ambiguous: insufficient distinctive lit intervals"
                continue
            permutation = orientations[best]
            geometry = Sampling(base.centers[permutation], [base.patches[i] for i in permutation])
            sampling[cid] = geometry
            entry.update(status="valid", reason="", orientation=best,
                         corners_xy=geometry.centers[[0, 11, 95, 84]].tolist())
            signals, _ = sample(camera_view(maximum, camera), geometry)
            write_overlay(directory / f"{cid}-grid.png", camera_view(maximum, camera), geometry,
                          signals, run.settings, "automatically located; physical LED indices")
    return result, sampling
