"""Portable CSV/JSON results and a self-contained HTML report."""

from html import escape
import json
import platform

import cv2
import numpy as np
import tqdm

from . import __version__
from .config import Run


def save_json(path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def display(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return escape(str(value))


def chart(rows: list[dict]) -> str:
    if not rows:
        return "<p>No cross-board comparison was configured.</p>"
    valid = [r for r in rows if r["status"] == "valid"]
    if not valid:
        return "<p>No valid representative-camera pairs. Inspect rejection counts and diagnostic images.</p>"
    xmin, xmax = min(r["reference_frame"] for r in rows), max(r["reference_frame"] for r in rows)
    ymax = max(1000, max(max(abs(r["lower_us"]), abs(r["upper_us"])) for r in valid)) * 1.1
    x = lambda v: 65 + 850 * (v - xmin) / max(1, xmax - xmin)
    y = lambda v: 145 - 110 * v / ymax
    elements = ['<svg viewBox="0 0 960 305" role="img" aria-label="Representative-camera offsets and conditional bounds">',
                '<line x1="65" y1="145" x2="915" y2="145" stroke="#bbc5ce"/>']
    for level in (-ymax, 0, ymax):
        elements.append(f'<text x="58" y="{y(level)+4:.2f}" text-anchor="end" font-size="12">{level:.0f}</text>')
    for r in valid:
        px, py = x(r["reference_frame"]), y(r["offset_us"])
        elements.append(f'<g><title>Frame {r["reference_frame"]}: {r["offset_us"]:.0f} us; '
                        f'[{r["lower_us"]:.0f}, {r["upper_us"]:.0f}]</title>'
                        f'<line x1="{px:.2f}" y1="{y(r["lower_us"]):.2f}" x2="{px:.2f}" y2="{y(r["upper_us"]):.2f}" stroke="#599fc8"/>'
                        f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="#076f9b"/></g>')
    for r in rows:
        if r["status"] != "valid":
            elements.append(f'<text x="{x(r["reference_frame"]):.2f}" y="274" fill="#b43232">×</text>')
    elements.extend([f'<text x="65" y="290" font-size="12">{xmin}</text>',
                     f'<text x="900" y="290" font-size="12">{xmax}</text>',
                     '<text x="390" y="300" font-size="12">Reference source frame index</text></svg>'])
    return "".join(elements)


def write_report(run: Run, pairs: list[dict], summary: dict) -> None:
    summary["software"] = {"camsync_check": __version__, "python": platform.python_version(),
                           "numpy": np.__version__, "opencv": cv2.__version__, "tqdm": tqdm.__version__}
    summary["sources"] = [{"id": s.id, "sync_board_id": s.board_id, "node_id": s.node_id,
                           "camera_ids": [c.id for c in s.cameras]} for s in run.sources]
    if run.comparison:
        summary["representatives"] = {"reference": run.comparison.reference_camera,
                                       "other": run.comparison.other_camera}
    save_json(run.output / "resolved.json", run.snapshot)
    save_json(run.output / "summary.json", summary)
    primary = [row for row in pairs if row["representative"]]
    stat = summary["representative_pair"]
    cards = "".join(f'<div><small>{label}</small><strong>{display(stat[field])}{unit}</strong></div>'
                    for label, field, unit in [
                        ("Median offset", "median_offset_us", " µs"),
                        ("Observed jitter, sample SD", "observed_jitter_std_us", " µs"),
                        ("Valid representative pairs", "valid_pairs", ""),
                        ("Total supplied pairs", "total_pairs", "")])
    headers = ["Kind", "Reference camera", "Other camera", "Median / µs", "Jitter SD / µs", "Valid / total"]
    table = '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>'
    for group in summary["camera_pairs"]:
        values = [group["kind"], group["reference_camera"], group["other_camera"], group["median_offset_us"],
                  group["observed_jitter_std_us"], f'{group["valid_pairs"]} / {group["total_pairs"]}']
        table += '<tr>' + ''.join(f'<td>{display(v)}</td>' for v in values) + '</tr>'
    table += '</tbody></table>'
    matrix = ""
    cross = [g for g in summary["camera_pairs"] if g["kind"] == "cross_board"]
    if cross:
        a_ids = list(dict.fromkeys(g["reference_camera"] for g in cross))
        b_ids = list(dict.fromkeys(g["other_camera"] for g in cross))
        lookup = {(g["reference_camera"], g["other_camera"]): g["median_offset_us"] for g in cross}
        matrix = '<h2>Cross-board median offsets / µs</h2><table><tr><th>A → B</th>'
        matrix += ''.join(f'<th>{escape(cid)}</th>' for cid in b_ids) + '</tr>'
        for cid in a_ids:
            matrix += f'<tr><th>{escape(cid)}</th>' + ''.join(f'<td>{display(lookup[cid, other])}</td>' for other in b_ids) + '</tr>'
        matrix += '</table>'
    images = "".join(f'<details><summary>{escape(c.id)} — first source frame</summary>'
                      f'<img src="diagnostics/{c.id}.png" alt="{escape(c.id)} LED sampling overlay"></details>'
                      for s in run.sources for c in s.cameras if (run.output / "diagnostics" / f"{c.id}.png").exists())
    localization = "".join(
        f'<details><summary>{escape(cid)}: {escape(entry["status"])} — {escape(entry["reason"])}</summary>'
        f'<img src="localization/{cid}-projection.png" alt="Temporal brightness range">'
        + (f'<img src="localization/{cid}-grid.png" alt="Located grid">' if entry["status"] == "valid" else "")
        + '</details>' for cid, entry in run.snapshot["localization"]["cameras"].items())
    limitations = ''.join(f'<li>{escape(item)}</li>' for item in summary["limitations"])
    rejection_text = escape(json.dumps(summary["frame_rejection_counts"], indent=2))
    decisions = escape(json.dumps(summary["pair_decision_counts"], indent=2))
    unmatched = escape(json.dumps(summary["unmatched_source_frames"], indent=2))
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Camera synchronization report</title>
<style>body{{font:15px system-ui;max-width:1100px;margin:36px auto;padding:0 22px;color:#173042;background:#fafbfd}}
h1{{margin-bottom:6px}}h2{{margin-top:30px}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.cards div{{background:#fff;border:1px solid #dce3e9;padding:18px;flex:1;min-width:180px}}small,strong{{display:block}}strong{{font-size:23px;margin-top:8px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:10px;border-bottom:1px solid #dce3e9;text-align:left}}th{{background:#eef3f7}}svg,img{{max-width:100%;height:auto}}details{{padding:12px;background:white;margin:8px 0}}pre{{white-space:pre-wrap}}.note{{background:#fff3d8;padding:15px}}</style>
<h1>Camera synchronization report</h1><p>Exposure-start offset; positive means the other camera exposes later.</p>
<div class="note">Conditional slot-level measurement. Prior: |offset| &lt; {run.settings.max_offset_us:g} µs.
Nominal slot: 250 µs. Conditional pair half-width: {(run.settings.boundary_slack + 1) * run.slot_us} µs.
Hardware accuracy has not been calibrated. This report does not prove the prior.</div>
<h2>Representative-camera comparison</h2><div class="cards">{cards}</div>
<p>Representatives: {escape(str(summary.get('representatives', 'not configured')))}.
Bars show conditional bounds; crosses show rejected pairs. An empty or partial report is not a synchronization pass.</p>
{chart(primary)}{matrix}<h2>Camera-pair statistics</h2>{table}
<h2>Quality and pairing</h2><p>Frame rejection counts:</p><pre>{rejection_text}</pre>
<p>Representative-pair decisions (tolerance: {display(run.settings.pass_tolerance_us)} µs):</p><pre>{decisions}</pre>
<p>Frames not included in supplied cross-board pairs:</p><pre>{unmatched}</pre>
<h2>Automatic R4 localization</h2>{localization}
<h2>LED sampling diagnostics</h2><p>Green: on; red: off; yellow: near threshold. These are the first supplied frames only.</p>{images}
<h2>Method limits</h2><ul>{limitations}</ul>
<p>Machine-readable results: <a href="frames.csv">frames.csv</a>, <a href="led_signals.csv">led_signals.csv</a>,
<a href="pairs.csv">pairs.csv</a>, <a href="summary.json">summary.json</a>, <a href="resolved.json">resolved.json</a>, <a href="localization.json">localization.json</a>.</p></html>'''
    (run.output / "report.html").write_text(content, encoding="utf-8")
