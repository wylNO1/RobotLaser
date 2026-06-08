"""2.5D toolpath: outer contour offset, hole circles, zigzag."""

from __future__ import annotations

import math
from typing import Any

from app.models.cad import PathPlanOptions, PathStrategy


def face_analyze_to_path_payload(face_analyze: dict[str, Any]) -> dict[str, Any]:
    """Adapt CadFaceAnalyzeResult JSON to the shape expected by generate_toolpath."""
    return {
        "summary": {"bbox": face_analyze["model_bbox"]},
        "outer_contours": face_analyze.get("outer_contours") or [],
        "contours": face_analyze.get("contours") or [],
        "wires": face_analyze.get("wires") or [],
        "polylines": face_analyze.get("polylines") or [],
        "holes": face_analyze.get("holes") or [],
    }


def generate_toolpath(analyze: dict[str, Any], options: PathPlanOptions) -> dict[str, Any]:
    bbox = analyze["summary"]["bbox"]
    z_cut = bbox["zmin"] + (bbox["zmax"] - bbox["zmin"]) * 0.5
    safe_z = options.safe_z if options.safe_z is not None else bbox["zmax"] + options.clearance_z

    segments: list[dict] = []
    total_len = 0.0

    strategy = options.strategy
    if isinstance(strategy, PathStrategy):
        strategy = strategy.value

    if strategy in ("outer_contour", "combined"):
        seg, ln = _outer_contour_path(analyze, safe_z, z_cut, options)
        if seg:
            segments.append(seg)
            total_len += ln

    if strategy in ("hole_circle", "combined"):
        for i, hole in enumerate(analyze.get("holes", [])):
            seg, ln = _hole_circle_path(hole, safe_z, z_cut, options, index=i)
            segments.append(seg)
            total_len += ln

    if strategy in ("zigzag", "combined"):
        seg, ln = _zigzag_path(bbox, safe_z, z_cut, options)
        segments.append(seg)
        total_len += ln

    feed = options.feed_cut or 800.0
    est_time = total_len / feed * 60.0 if feed > 0 else None

    return {
        "schema_version": "1.0",
        "unit": "mm",
        "strategy": strategy,
        "segments": segments,
        "total_length": total_len,
        "estimated_time_s": est_time,
    }


def _outer_contour_path(analyze, safe_z, z_cut, options):
    outer_ids = analyze.get("outer_contours") or []
    contours = {c["id"]: c for c in analyze.get("contours", [])}
    wires = {w["id"]: w for w in analyze.get("wires", [])}
    polys = {p["id"]: p for p in analyze.get("polylines", [])}
    for oid in outer_ids:
        poly_id = None
        c = contours.get(oid)
        if c:
            poly_id = c.get("polyline_id")
        else:
            w = wires.get(oid)
            poly_id = w.get("polyline_id") if w else None
        if not poly_id:
            continue
        poly = polys.get(poly_id)
        if not poly or len(poly["points"]) < 2:
            continue
        pts = [_lift(p, safe_z) for p in poly["points"]]
        pts.append(_lift(poly["points"][0], safe_z))
        cut = [_lift(p, z_cut) for p in poly["points"]]
        if cut and _dist(cut[0], cut[-1]) > 1e-3:
            cut.append(cut[0])
        path = pts + cut
        ln = _polyline_length(path)
        return {
            "id": "seg_outer_contour",
            "strategy": "outer_contour",
            "feed": options.feed_cut,
            "points": path,
        }, ln
    return None, 0.0


def _hole_circle_path(hole, safe_z, z_cut, options, index: int):
    c = hole["center"]
    r = (hole.get("diameter") or options.tool_diameter) * 0.5
    if options.hole_lead_in:
        r = max(r - options.tool_diameter * 0.25, options.tool_diameter * 0.1)
    n = max(16, int(2 * math.pi * r / max(options.step_over, 0.5)))
    path = [_pt(c["x"], c["y"], safe_z)]
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        path.append(_pt(c["x"] + r * math.cos(t), c["y"] + r * math.sin(t), z_cut))
    path.append(_pt(c["x"], c["y"], safe_z))
    ln = _polyline_length(path)
    return {
        "id": f"seg_hole_{index}",
        "strategy": "hole_circle",
        "feed": options.feed_cut,
        "points": path,
    }, ln


def _zigzag_path(bbox, safe_z, z_cut, options):
    xmin, xmax = bbox["xmin"], bbox["xmax"]
    ymin, ymax = bbox["ymin"], bbox["ymax"]
    step = options.step_over
    path: list[dict] = []
    y = ymin
    flip = False
    while y <= ymax + 1e-6:
        if not flip:
            path.append(_pt(xmin, y, safe_z))
            path.append(_pt(xmin, y, z_cut))
            path.append(_pt(xmax, y, z_cut))
            path.append(_pt(xmax, y, safe_z))
        else:
            path.append(_pt(xmax, y, safe_z))
            path.append(_pt(xmax, y, z_cut))
            path.append(_pt(xmin, y, z_cut))
            path.append(_pt(xmin, y, safe_z))
        y += step
        flip = not flip
    ln = _polyline_length(path)
    return {
        "id": "seg_zigzag",
        "strategy": "zigzag",
        "feed": options.feed_cut,
        "points": path,
    }, ln


def _lift(p, z):
    return {"x": p["x"], "y": p["y"], "z": z}


def _pt(x, y, z):
    return {"x": float(x), "y": float(y), "z": float(z)}


def _dist(a, b):
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _polyline_length(pts):
    return sum(_dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
