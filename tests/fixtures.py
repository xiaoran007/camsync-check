"""Deterministic optical fixtures with geometry and exposure defined independently."""

import json
from pathlib import Path

import cv2
import numpy as np


WIDTH, HEIGHT = 420, 300
CORNERS = [[170, 120], [302, 120], [302, 204], [170, 204]]
CENTERS = np.float32([(170 + 12 * column, 120 + 12 * row) for row in range(8) for column in range(12)])


def reference(root: Path) -> np.ndarray:
    image = np.full((HEIGHT, WIDTH), 45, np.uint8)
    rng = np.random.default_rng(42096)
    for _ in range(350):
        x, y = rng.integers([18, 18], [WIDTH - 18, HEIGHT - 18])
        if 145 <= x <= 328 and 95 <= y <= 230:
            continue
        radius = int(rng.integers(2, 8))
        cv2.circle(image, (int(x), int(y)), radius, int(rng.integers(70, 235)), -1)
        cv2.line(image, (int(x), int(y)), (int(x) + radius, int(y) + radius), 20, 1)
    cv2.putText(image, "R4 REFERENCE", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 210, 2)
    cv2.imwrite(str(root / "reference.png"), image)
    data = {"schema_version": 1, "kind": "reference", "board_id": "uno_r4_wifi", "image": "reference.png",
            "image_size": [WIDTH, HEIGHT], "led_corners_xy": CORNERS,
            "feature_polygon_xy": [[8, 8], [411, 8], [411, 291], [8, 291]],
            "exclude_polygons_xy": [[[145, 95], [328, 95], [328, 230], [145, 230]]],
            "provenance": {"creator": "Deterministic test fixture"}}
    (root / "reference.json").write_text(json.dumps(data))
    return image


def exposure(image: np.ndarray, start_us: float, duration_us: float) -> np.ndarray:
    frame = image.copy()
    # Integrate each physical LED's rectangular pulse over the requested exposure.
    for index, (x, y) in enumerate(CENTERS):
        overlap = 0.0
        for cycle in range(-2, 4):
            begin = cycle * 24000 + index * 250
            overlap += max(0, min(start_us + duration_us, begin + 250) - max(start_us, begin))
        if overlap:
            value = min(245, round(45 + 160 * overlap / 250))
            cv2.circle(frame, (int(x), int(y)), 3, value, -1)
    return frame


def config(root: Path, nframes: int = 4, same_node: bool = True) -> dict:
    repository = Path(__file__).resolve().parents[1]
    data = json.loads((repository / "configs/two-b0267.json").read_text())
    data["output"] = "result"
    data["localization"] = {"reference": "reference.json", "max_frames": nframes, "min_valid_frames": 2}
    data["comparison"]["frame_pairs"] = [[i, i] for i in range(nframes)]
    for source_index, source in enumerate(data["sources"]):
        source["frames"] = [f"source_{source_index}_{i}.png" for i in range(nframes)]
        source["node_id"] = "node_0" if same_node else f"node_{source_index}"
    (root / "run.json").write_text(json.dumps(data))
    return data


def capture(root: Path, invalid_camera: bool = False) -> dict:
    base = reference(root)
    data = config(root)
    starts = [22500, 4500, 9500, 14500]
    delays = [[0, 250, 0, -250], [1000, 1250, 1000, 750]]
    for source_index, source in enumerate(data["sources"]):
        for index, path in enumerate(source["frames"]):
            composite = np.full((800, 5120), 25, np.uint8)
            for camera in range(4):
                if invalid_camera and source_index == 1 and camera == 3:
                    continue
                view = exposure(base, starts[index] + delays[source_index][camera], 1500 + 250 * (index % 2))
                x, y = camera * 1280 + 100, 100
                composite[y:y + HEIGHT, x:x + WIDTH] = view
            cv2.imwrite(str(root / path), composite)
    return data
