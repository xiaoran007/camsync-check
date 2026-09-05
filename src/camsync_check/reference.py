"""Offline board reference assets and SIFT correspondence geometry."""

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import json

import cv2
import numpy as np

from .config import Camera, ConfigError, Run, identifier, keys, resolve
from .vision import Sampling, make_sampling


@dataclass
class Reference:
    image: np.ndarray
    mask: np.ndarray
    corners: np.ndarray
    metadata: dict


def load_reference(run: Run) -> Reference:
    name = run.localization.reference
    if name.startswith("builtin:"):
        resource = files("camsync_check").joinpath("references", identifier(name[8:], "reference") + ".json")
    else:
        resource = resolve(run.path.parent, name)
    data = json.loads(resource.read_text(encoding="utf-8"))
    keys(data, {"schema_version", "kind", "board_id", "image", "image_size", "led_corners_xy",
                "feature_polygon_xy", "exclude_polygons_xy", "provenance"}, set(), "reference")
    if data["schema_version"] != 1 or data["kind"] != "reference" or data["board_id"] != "uno_r4_wifi":
        raise ConfigError("Expected a version 1 UNO R4 WiFi reference")
    if not isinstance(data["image"], str) or not data["image"]:
        raise ConfigError("reference.image must be a nonempty path relative to its JSON file")
    encoded = resource.parent.joinpath(data["image"]).read_bytes()
    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or list(image.shape[::-1]) != data["image_size"]:
        raise ConfigError("Reference image cannot be decoded or differs from image_size")
    height, width = image.shape
    geometry = make_sampling(data["led_corners_xy"], Camera("reference", (0, 0, width, height)))
    mask = np.zeros_like(image)

    def polygon(value) -> np.ndarray:
        points = np.asarray(value, dtype=float)
        if (points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all()
                or np.any(points < 0) or np.any(points[:, 0] >= width) or np.any(points[:, 1] >= height)):
            raise ConfigError("Reference polygons must contain finite points inside the image")
        return np.rint(points).astype(np.int32)

    cv2.fillPoly(mask, [polygon(data["feature_polygon_xy"])], 255)
    if not isinstance(data["exclude_polygons_xy"], list):
        raise ConfigError("exclude_polygons_xy must be a list")
    for excluded in data["exclude_polygons_xy"]:
        cv2.fillPoly(mask, [polygon(excluded)], 0)
    # Exclude the LED grid even if a custom reference omits its exclusion polygon.
    cv2.fillConvexPoly(mask, np.rint(geometry.centers[[0, 11, 95, 84]]).astype(np.int32), 0)
    if np.count_nonzero(mask) < 100:
        raise ConfigError("Reference feature mask is empty or too small")
    metadata = {"reference": name, "definition": data, "image_sha256": hashlib.sha256(encoded).hexdigest()}
    return Reference(image, mask, geometry.centers[[0, 11, 95, 84]], metadata)


def grid_pitch(geometry: Sampling) -> float:
    grid = geometry.centers.reshape(8, 12, 2)
    return float(min(np.linalg.norm(np.diff(grid, axis=1), axis=2).min(),
                     np.linalg.norm(np.diff(grid, axis=0), axis=2).min()))


class ReferenceMatcher:
    """Cache original and reflected reference descriptors; never infer orientation from LEDs."""

    def __init__(self, reference: Reference):
        self.reference = reference
        self.sift = cv2.SIFT_create(nfeatures=3000, contrastThreshold=0.025)
        self.variants = []
        for mirrored in (False, True):
            image = np.fliplr(reference.image).copy() if mirrored else reference.image
            mask = np.fliplr(reference.mask).copy() if mirrored else reference.mask
            keypoints, descriptors = self.sift.detectAndCompute(image, mask)
            if descriptors is None or len(keypoints) < 12:
                raise ConfigError("Reference has fewer than 12 usable SIFT features")
            points = np.float32([point.pt for point in keypoints])
            if mirrored:
                points[:, 0] = image.shape[1] - 1 - points[:, 0]
            self.variants.append((mirrored, points, descriptors))

    def locate(self, view: np.ndarray, camera: Camera) -> tuple[Sampling, dict]:
        keypoints, descriptors = self.sift.detectAndCompute(view, None)
        if descriptors is None or len(keypoints) < 12:
            raise ConfigError("reference_not_found: fewer than 12 image features")
        destinations = np.float32([point.pt for point in keypoints])
        candidates = []
        for mirrored, reference_points, reference_descriptors in self.variants:
            neighbors = cv2.BFMatcher(cv2.NORM_L2).knnMatch(reference_descriptors, descriptors, k=2)
            # Each destination contributes once, preventing repeated texture from inflating support.
            good = {}
            for pair in neighbors:
                if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
                    match = pair[0]
                    if match.trainIdx not in good or match.distance < good[match.trainIdx].distance:
                        good[match.trainIdx] = match
            matches = list(good.values())
            if len(matches) < 12:
                continue
            source = np.float32([reference_points[m.queryIdx] for m in matches])
            target = np.float32([destinations[m.trainIdx] for m in matches])
            transform, inlier_mask = cv2.findHomography(source, target, cv2.RANSAC, 2.0)
            if transform is None or inlier_mask is None:
                continue
            inliers = inlier_mask.ravel().astype(bool)
            count = int(inliers.sum())
            if count < 12 or count / len(matches) < 0.5:
                continue
            coverage = cv2.contourArea(cv2.convexHull(source[inliers])) / np.count_nonzero(self.reference.mask)
            if coverage < 0.05:
                continue
            corners = cv2.perspectiveTransform(self.reference.corners.reshape(1, 4, 2), transform)[0]
            try:
                geometry = make_sampling(corners, camera)
            except ConfigError:
                continue
            estimated = cv2.perspectiveTransform(source[inliers].reshape(1, -1, 2), transform)[0]
            residual = float(np.linalg.norm(estimated - target[inliers], axis=1).max())
            if residual > min(3.0, 0.3 * grid_pitch(geometry)):
                continue
            candidates.append((geometry, {"mirrored": mirrored, "matches": len(matches), "inliers": count,
                                           "feature_coverage": float(coverage), "max_reprojection_error_px": residual}))
        if not candidates:
            raise ConfigError("reference_not_found: insufficient consistent, distributed SIFT matches")
        candidates.sort(key=lambda item: item[1]["inliers"], reverse=True)
        best = candidates[0]
        for other, _ in candidates[1:]:
            if np.linalg.norm(best[0].centers - other.centers, axis=1).max() > 0.25 * grid_pitch(best[0]):
                raise ConfigError("ambiguous_reference: conflicting original/reflected matches")
        return best
