"""Grid-based LED sampling and circular binary-run decoding."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import Camera, ConfigError, Settings, Source


@dataclass
class Sampling:
    centers: np.ndarray
    patches: list[tuple[slice, slice, np.ndarray, np.ndarray]]


def read_frame(path: Path, source: Source) -> np.ndarray:
    frame = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if frame is None:
        raise ConfigError(f"Cannot decode image: {path}")
    if frame.dtype != np.uint8 or frame.shape != (source.height, source.width):
        raise ConfigError(f"{path}: expected uint8 grayscale {source.width}x{source.height}, "
                          f"got {frame.dtype} {frame.shape}")
    return frame


def camera_view(frame: np.ndarray, camera: Camera) -> np.ndarray:
    x, y, w, h = camera.crop
    return frame[y:y + h, x:x + w]


def make_sampling(corners, camera: Camera) -> Sampling:
    points = np.asarray(corners, dtype=np.float64)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ConfigError(f"{camera.id}: four finite LED-center coordinates are required")
    width, height = camera.crop[2:]
    if (np.any(points < 0) or np.any(points[:, 0] >= width) or np.any(points[:, 1] >= height)
            or not cv2.isContourConvex(points.astype(np.float32))):
        raise ConfigError(f"{camera.id}: corners must be an ordered convex quadrilateral inside its view")
    logical = np.float32([[0, 0], [11, 0], [11, 7], [0, 7]])
    transform = cv2.getPerspectiveTransform(logical, points.astype(np.float32))
    grid = np.float32([[(x, y) for y in range(8) for x in range(12)]])
    centers = cv2.perspectiveTransform(grid, transform)[0]
    if not np.isfinite(centers).all():
        raise ConfigError(f"{camera.id}: degenerate target geometry")
    patches = []
    for index, (cx, cy) in enumerate(centers):
        row, column = divmod(index, 12)
        neighbors = []
        if column: neighbors.append(index - 1)
        if column < 11: neighbors.append(index + 1)
        if row: neighbors.append(index - 12)
        if row < 7: neighbors.append(index + 12)
        pitch = float(np.linalg.norm(centers[neighbors] - centers[index], axis=1).min())
        if pitch < 6:
            raise ConfigError(f"{camera.id}: LED spacing below 6 pixels; enlarge the target in the image")
        radius = 0.44 * pitch
        x0, x1 = int(np.floor(cx - radius)), int(np.ceil(cx + radius)) + 1
        y0, y1 = int(np.floor(cy - radius)), int(np.ceil(cy + radius)) + 1
        if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
            raise ConfigError(f"{camera.id}: sampling region for LED {index} extends outside the view")
        yy, xx = np.mgrid[y0:y1, x0:x1]
        distance = ((xx - cx) ** 2 + (yy - cy) ** 2) / pitch ** 2
        foreground = distance <= 0.22 ** 2
        background = (distance >= 0.32 ** 2) & (distance <= 0.44 ** 2)
        if not foreground.any() or not background.any():
            raise ConfigError(f"{camera.id}: empty LED sampling mask")
        patches.append((slice(y0, y1), slice(x0, x1), foreground, background))
    return Sampling(centers, patches)


def sample(view: np.ndarray, sampling: Sampling) -> tuple[np.ndarray, np.ndarray]:
    signals, saturated = [], []
    for ys, xs, foreground, background in sampling.patches:
        patch = view[ys, xs]
        pixels = patch[foreground]
        signals.append(float(np.mean(pixels)) - float(np.median(patch[background])))
        saturated.append(float(np.mean(pixels == 255)))
    return np.asarray(signals), np.asarray(saturated)


def decode(signals: np.ndarray, saturated: np.ndarray, settings: Settings, slot_us: int) -> dict:
    on = signals >= settings.threshold
    count = int(on.sum())
    result = {"status": "invalid", "reason": "", "first_slot": None, "last_slot": None,
              "lit_count": count, "phase_start_us": None, "phase_end_us": None,
              "exposure_min_us": None, "exposure_max_us": None}
    if np.any(np.abs(signals - settings.threshold) <= settings.margin):
        result["reason"] = "threshold_ambiguous"
    elif np.any(saturated[on] > settings.max_saturated_fraction):
        result["reason"] = "saturated"
    elif count == 0:
        result["reason"] = "no_lit_leds"
    elif count + 2 * settings.boundary_slack >= len(on):
        result["reason"] = "full_or_near_full_cycle"
    else:
        starts = np.flatnonzero(on & ~np.roll(on, 1))
        if len(starts) != 1:
            result["reason"] = "disconnected_lit_intervals"
        else:
            first = int(starts[0])
            # Bounds allow the explicitly configured number of missed edge slots.
            start_low = (first - settings.boundary_slack) * slot_us
            start_high = (first + 1) * slot_us
            end_low = (first + count - 1) * slot_us
            end_high = (first + count + settings.boundary_slack) * slot_us
            result.update(status="valid", reason="", first_slot=first,
                          last_slot=(first + count - 1) % len(on),
                          phase_start_us=(start_low + start_high) / 2 % (len(on) * slot_us),
                          phase_end_us=(end_low + end_high) / 2 % (len(on) * slot_us),
                          exposure_min_us=max(0, end_low - start_high),
                          exposure_max_us=end_high - start_low)
    return result


def write_overlay(path: Path, view: np.ndarray, sampling: Sampling, signals: np.ndarray,
                  settings: Settings, reason: str) -> None:
    canvas = cv2.cvtColor(view, cv2.COLOR_GRAY2BGR)
    for index, (x, y) in enumerate(sampling.centers):
        color = (0, 200, 0) if signals[index] >= settings.threshold else (80, 80, 230)
        if abs(signals[index] - settings.threshold) <= settings.margin:
            color = (0, 200, 255)
        point = (round(float(x)), round(float(y)))
        cv2.circle(canvas, point, 3, color, 1, cv2.LINE_AA)
        cv2.putText(canvas, str(index), (point[0] + 3, point[1] - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1, cv2.LINE_AA)
    cv2.putText(canvas, reason or "valid interval", (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (0, 200, 255), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), canvas):
        raise OSError(f"Could not write diagnostic image: {path}")
