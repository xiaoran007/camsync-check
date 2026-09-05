"""R4 reference matching followed by optical grid refinement."""

import cv2
import numpy as np
from tqdm import tqdm

from .config import Camera, ConfigError, Run
from .reference import ReferenceMatcher, grid_pitch, load_reference
from .vision import Sampling, camera_view, make_sampling, read_frame, sample, write_overlay


def refine_grid(projection: np.ndarray, camera: Camera, initial: Sampling,
                threshold: float) -> tuple[Sampling, dict]:
    pitch = grid_pitch(initial)
    radius = 0.4 * pitch
    logical, observed = [], []
    for index, (cx, cy) in enumerate(initial.centers):
        x0, x1 = max(0, int(cx - radius)), min(projection.shape[1], int(cx + radius) + 2)
        y0, y1 = max(0, int(cy - radius)), min(projection.shape[0], int(cy + radius) + 2)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        weights = np.maximum(projection[y0:y1, x0:x1].astype(float) - threshold, 0)
        weights[(xx - cx) ** 2 + (yy - cy) ** 2 > radius ** 2] = 0
        if np.count_nonzero(weights) < 3:
            continue
        logical.append((index % 12, index // 12))
        observed.append((float((weights * xx).sum() / weights.sum()),
                         float((weights * yy).sum() / weights.sum())))
    if len(logical) < 12 or cv2.contourArea(cv2.convexHull(np.float32(logical))) < 8:
        raise ConfigError("insufficient_led_evidence: need 12 changing LEDs distributed across the grid")
    logical, observed = np.float32(logical), np.float32(observed)
    transform, _ = cv2.findHomography(logical, observed, method=0)
    if transform is None:
        raise ConfigError("invalid_led_geometry: could not refine grid")
    projected = cv2.perspectiveTransform(logical.reshape(1, -1, 2), transform)[0]
    error = float(np.linalg.norm(projected - observed, axis=1).max())
    corners = cv2.perspectiveTransform(np.float32([[[0, 0], [11, 0], [11, 7], [0, 7]]]), transform)[0]
    refined = make_sampling(corners, camera)
    shift = float(np.linalg.norm(refined.centers - initial.centers, axis=1).max())
    if error > 0.2 * pitch or shift > 0.3 * pitch:
        raise ConfigError("invalid_led_geometry: refinement disagrees with the reference grid")
    return refined, {"observed_leds": len(logical), "max_led_residual_px": error,
                     "max_refinement_shift_px": shift}


def localize(run: Run) -> tuple[dict, dict[str, Sampling | None]]:
    reference = load_reference(run)
    matcher = ReferenceMatcher(reference)
    directory = run.output / "localization"
    directory.mkdir(parents=True, exist_ok=True)
    result = {"schema_version": 1, "protocol": "r4-rowmajor96-v2", "method": "sift_reference",
              "reference": reference.metadata, "cameras": {}}
    sampling = {}
    for source in run.sources:
        count = min(len(source.frames), run.localization.max_frames)
        indices = np.linspace(0, len(source.frames) - 1, count, dtype=int).tolist()
        maximum, minimum = None, None
        found = {camera.id: [] for camera in source.cameras}
        for camera in source.cameras:
            sampling[camera.id] = None
            result["cameras"][camera.id] = {"status": "invalid", "reason": "", "frames": [],
                                           "view_size": list(camera.crop[2:]), "sampled_frame_indices": indices}
        with tqdm(total=count * len(source.cameras), desc=f"Locate {source.id}: SIFT", unit="view") as progress:
            for index in indices:
                frame = read_frame(source.frames[index], source)
                if maximum is None:
                    maximum, minimum = frame.copy(), frame.copy()
                else:
                    np.maximum(maximum, frame, out=maximum)
                    np.minimum(minimum, frame, out=minimum)
                for camera in source.cameras:
                    record = {"frame_index": index, "status": "invalid"}
                    try:
                        geometry, evidence = matcher.locate(camera_view(frame, camera), camera)
                    except ConfigError as error:
                        record["reason"] = str(error)
                    else:
                        found[camera.id].append(geometry)
                        record.update(evidence, status="valid")
                    result["cameras"][camera.id]["frames"].append(record)
                    progress.update(1)
        projection = maximum - minimum
        for camera in source.cameras:
            cid = camera.id
            entry = result["cameras"][cid]
            view = camera_view(projection, camera)
            if not cv2.imwrite(str(directory / f"{cid}-projection.png"), view):
                raise OSError(f"Could not write projection for {cid}")
            geometries = found[cid]
            if any(frame.get("reason", "").startswith("ambiguous_reference") for frame in entry["frames"]):
                entry["reason"] = "ambiguous_reference"
                continue
            if len(geometries) < run.localization.min_valid_frames:
                entry["reason"] = "insufficient_reference_frames"
                continue
            corners = np.median([g.centers[[0, 11, 95, 84]] for g in geometries], axis=0)
            try:
                initial = make_sampling(corners, camera)
            except ConfigError:
                entry["reason"] = "moving_or_inconsistent_reference"
                continue
            disagreement = max(float(np.linalg.norm(g.centers - initial.centers, axis=1).max()) for g in geometries)
            if disagreement > 0.3 * grid_pitch(initial):
                entry["reason"] = "moving_or_inconsistent_reference"
                continue
            try:
                geometry, evidence = refine_grid(view, camera, initial, run.settings.threshold)
            except ConfigError as error:
                entry["reason"] = str(error)
                continue
            sampling[cid] = geometry
            entry.update(evidence, status="valid", reason="", corners_xy=geometry.centers[[0, 11, 95, 84]].tolist(),
                         max_reference_disagreement_px=disagreement)
            signals, _ = sample(camera_view(maximum, camera), geometry)
            write_overlay(directory / f"{cid}-grid.png", camera_view(maximum, camera), geometry,
                          signals, run.settings, "reference orientation; row-major LED indices")
    return result, sampling
