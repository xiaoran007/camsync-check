"""Explicit run configuration and packaged hardware profiles."""

from dataclasses import dataclass
from importlib.resources import files
import json
import math
from pathlib import Path
import re


class ConfigError(ValueError):
    """An invalid or unsupported input configuration."""


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: expected a JSON object")
    return value


def keys(value: dict, required: set, optional: set, location: str) -> None:
    if not isinstance(value, dict):
        raise ConfigError(f"{location}: expected an object")
    missing, extra = required - value.keys(), value.keys() - required - optional
    if missing or extra:
        raise ConfigError(f"{location}: missing {sorted(missing)}, unknown {sorted(extra)}")


def number(value, location: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{location}: expected a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ConfigError(f"{location}: expected {minimum} <= value <= {maximum}")
    return float(value)


def integer(value, location: str, minimum: int, maximum: int) -> int:
    number(value, location, minimum, maximum)
    if not isinstance(value, int):
        raise ConfigError(f"{location}: expected an integer")
    return value


def identifier(value, location: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ConfigError(f"{location}: use letters, numbers, underscores, or hyphens")
    return value


def resolve(base: Path, value) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigError("File paths must be nonempty strings")
    return (base / value).resolve()


def profile(reference: str, base: Path, kind: str) -> dict:
    if not isinstance(reference, str):
        raise ConfigError("Profile references must be strings")
    if reference.startswith("builtin:"):
        name = identifier(reference.removeprefix("builtin:"), "builtin profile")
        resource = files("camsync_check").joinpath("profiles", f"{name}.json")
        result = json.loads(resource.read_text(encoding="utf-8"))
    else:
        result = read_json(resolve(base, reference))
    if not isinstance(result, dict) or result.get("schema_version") != 1 or result.get("kind") != kind:
        raise ConfigError(f"{reference}: expected a version 1 {kind} profile")
    return result


@dataclass(frozen=True)
class Camera:
    id: str
    crop: tuple[int, int, int, int]


@dataclass(frozen=True)
class Source:
    id: str
    board_id: str
    node_id: str
    width: int
    height: int
    cameras: tuple[Camera, ...]
    frames: tuple[Path, ...]
    frame_period_us: float | None


@dataclass(frozen=True)
class Settings:
    threshold: float
    margin: float
    max_saturated_fraction: float
    boundary_slack: int
    max_offset_us: float
    resolution_us: float
    pass_tolerance_us: float | None


@dataclass(frozen=True)
class Comparison:
    reference: str
    other: str
    reference_camera: str
    other_camera: str
    pairs: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Localization:
    max_frames: int
    min_valid_frames: int
    orientation_margin: int


@dataclass(frozen=True)
class Run:
    path: Path
    output: Path
    localization: Localization
    scan_order: tuple[int, ...]
    sources: tuple[Source, ...]
    settings: Settings
    comparison: Comparison | None
    snapshot: dict
    slot_us: int = 250
    led_count: int = 96


def load_config(path: Path) -> Run:
    path = path.resolve()
    data = read_json(path)
    keys(data, {"schema_version", "target", "sources", "localization", "analysis", "output"},
         {"comparison"}, "run")
    if data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    target = data["target"]
    keys(target, {"profile", "protocol", "slot_us"}, set(), "target")
    target_profile = profile(target["profile"], path.parent, "target")
    if (target_profile.get("board_id") != "uno_r4_wifi"
            or target_profile.get("matrix", {}).get("rows") != 8
            or target_profile.get("matrix", {}).get("columns") != 12
            or target_profile.get("matrix", {}).get("led_count") != 96
            or target_profile.get("matrix", {}).get("indexing") != "row_major_zero_based"
            or target["protocol"] != "r4-permuted96-v1"
            or target["slot_us"] != 250):
        raise ConfigError("This version implements UNO R4 WiFi r4-permuted96-v1 at 250 us only")
    canonical = profile("builtin:uno_r4_wifi", path.parent, "target")
    if any(target_profile.get(key) != canonical[key] for key in ("protocol", "slot_us", "scan_order")):
        raise ConfigError("Target protocol and scan order must match the firmware's built-in R4 profile")
    loc = data["localization"]
    keys(loc, {"max_frames", "min_valid_frames", "orientation_margin"}, set(), "localization")
    max_frames = integer(loc["max_frames"], "localization.max_frames", 3, 10000)
    localization = Localization(max_frames,
        integer(loc["min_valid_frames"], "localization.min_valid_frames", 3, max_frames),
        integer(loc["orientation_margin"], "localization.orientation_margin", 1, max_frames))
    a = data["analysis"]
    keys(a, {"on_threshold", "threshold_margin", "max_saturated_fraction",
             "boundary_slack_slots", "max_abs_offset_us", "target_resolution_us", "pass_tolerance_us"},
         set(), "analysis")
    threshold = number(a["on_threshold"], "on_threshold", 1, 254)
    margin = number(a["threshold_margin"], "threshold_margin", 0, threshold - 0.01)
    slack = integer(a["boundary_slack_slots"], "boundary_slack_slots", 0, 4)
    max_offset = number(a["max_abs_offset_us"], "max_abs_offset_us", 1, 11999)
    resolution = number(a["target_resolution_us"], "target_resolution_us", 1, 10000)
    tolerance = a["pass_tolerance_us"]
    if tolerance is not None:
        tolerance = number(tolerance, "pass_tolerance_us", 0, max_offset)
    settings = Settings(threshold, margin,
                        number(a["max_saturated_fraction"], "max_saturated_fraction", 0, 1),
                        slack, max_offset, resolution, tolerance)
    if (slack + 1) * 250 > resolution:
        raise ConfigError("The configured conditional timing half-width exceeds target_resolution_us")
    if not isinstance(data["sources"], list) or not data["sources"]:
        raise ConfigError("sources must be a nonempty list")
    sources, resolved_profiles = [], {"target": target_profile}
    source_ids, camera_ids, board_ids = set(), set(), set()
    for raw in data["sources"]:
        keys(raw, {"id", "sync_board_id", "node_id", "profile", "camera_ids", "frames", "exposure"},
             {"frame_period_us"}, "source")
        sid = identifier(raw["id"], "source.id")
        bid = identifier(raw["sync_board_id"], f"{sid}.sync_board_id")
        nid = identifier(raw["node_id"], f"{sid}.node_id")
        if sid in source_ids or bid in board_ids:
            raise ConfigError("Source and synchronization-board IDs must be unique")
        source_ids.add(sid)
        board_ids.add(bid)
        p = profile(raw["profile"], path.parent, "camera")
        keys(p, {"schema_version", "kind", "model", "image", "shutter", "views"}, set(), sid)
        keys(p["image"], {"width", "height", "channels", "dtype"}, set(), f"{sid}.image")
        if p["shutter"] != "global" or p["image"]["channels"] != 1 or p["image"]["dtype"] != "uint8":
            raise ConfigError(f"{sid}: only global-shutter uint8 grayscale profiles are supported")
        width = integer(p["image"]["width"], f"{sid}.width", 1, 65536)
        height = integer(p["image"]["height"], f"{sid}.height", 1, 65536)
        if not isinstance(p["views"], list) or not p["views"]:
            raise ConfigError(f"{sid}.views must be nonempty")
        if not isinstance(raw["camera_ids"], dict):
            raise ConfigError(f"{sid}.camera_ids must be an object")
        cameras, view_ids = [], set()
        for view in p["views"]:
            keys(view, {"id", "crop_xywh"}, set(), f"{sid}.view")
            vid = identifier(view["id"], "view.id")
            if vid in view_ids or vid not in raw["camera_ids"]:
                raise ConfigError(f"{sid}: duplicate or unmapped view {vid}")
            view_ids.add(vid)
            cid = identifier(raw["camera_ids"][vid], "camera_id")
            if cid in camera_ids:
                raise ConfigError(f"Duplicate camera ID: {cid}")
            camera_ids.add(cid)
            crop = view["crop_xywh"]
            if not isinstance(crop, list) or len(crop) != 4:
                raise ConfigError(f"{cid}: crop_xywh must have four integers")
            x, y, w, h = (integer(v, f"{cid}.crop", 0 if i < 2 else 1, 65536)
                          for i, v in enumerate(crop))
            if x + w > width or y + h > height:
                raise ConfigError(f"{cid}: crop exceeds configured image size")
            cameras.append(Camera(cid, (x, y, w, h)))
        if raw["camera_ids"].keys() != view_ids:
            raise ConfigError(f"{sid}: camera_ids must map exactly the profile views")
        frame_list = raw["frames"]
        if not isinstance(frame_list, list) or not frame_list:
            raise ConfigError(f"{sid}: frames must be a nonempty ordered list")
        frame_paths = tuple(resolve(path.parent, item) for item in frame_list)
        if len(set(frame_paths)) != len(frame_paths):
            raise ConfigError(f"{sid}: duplicate input paths; preserve distinct captured files")
        exposure = raw["exposure"]
        keys(exposure, {"value_us", "provenance"}, set(), f"{sid}.exposure")
        if exposure["provenance"] not in {"unknown", "requested", "reported", "calibrated"}:
            raise ConfigError(f"{sid}: invalid exposure provenance")
        if exposure["value_us"] is not None:
            number(exposure["value_us"], f"{sid}.exposure.value_us", 0.01, 1e9)
        if (exposure["value_us"] is None) != (exposure["provenance"] == "unknown"):
            raise ConfigError(f"{sid}: unknown exposure must use null and vice versa")
        period = raw.get("frame_period_us")
        if period is not None:
            period = number(period, f"{sid}.frame_period_us", 1, 1e9)
        sources.append(Source(sid, bid, nid, width, height, tuple(cameras), frame_paths, period))
        resolved_profiles[sid] = p
    comparison = None
    if "comparison" in data:
        c = data["comparison"]
        keys(c, {"reference_source", "other_source", "reference_camera", "other_camera", "frame_pairs"},
             set(), "comparison")
        lookup = {source.id: source for source in sources}
        if c["reference_source"] not in lookup or c["other_source"] not in lookup:
            raise ConfigError("comparison refers to an unknown source")
        left, right = lookup[c["reference_source"]], lookup[c["other_source"]]
        if left.id == right.id:
            raise ConfigError("comparison requires two different sources")
        if c["reference_camera"] not in {v.id for v in left.cameras} or c["other_camera"] not in {v.id for v in right.cameras}:
            raise ConfigError("Representatives must belong to their respective sources")
        if not isinstance(c["frame_pairs"], list) or not c["frame_pairs"]:
            raise ConfigError("comparison.frame_pairs must be nonempty")
        pairs = []
        for pair in c["frame_pairs"]:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ConfigError("Each frame pair must contain two zero-based indices")
            n = integer(pair[0], "reference frame index", 0, len(left.frames) - 1)
            m = integer(pair[1], "other frame index", 0, len(right.frames) - 1)
            if pairs and (n <= pairs[-1][0] or m <= pairs[-1][1]):
                raise ConfigError("Frame pairs must be strictly increasing and one-to-one")
            pairs.append((n, m))
        comparison = Comparison(left.id, right.id, c["reference_camera"], c["other_camera"], tuple(pairs))
    snapshot = {"configuration": data, "configuration_path": str(path), "resolved_profiles": resolved_profiles}
    return Run(path, resolve(path.parent, data["output"]), localization, tuple(canonical["scan_order"]),
               tuple(sources), settings, comparison, snapshot)
