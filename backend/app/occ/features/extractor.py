"""Orchestrate point / face / wire / hole / pocket extraction."""

from __future__ import annotations

import math
from typing import Any

from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop

from app.models.cad import CadAnalyzeOptions, WorkPlane
from app.occ.discretize import wire_length, wire_location_on_face, wire_to_polyline
from app.occ.features.contour_classifier import classify_wire_contour
from app.occ.geometry_utils import (
    face_area,
    face_surface_info,
    face_wires,
    iterate_faces,
    project_point,
    shape_bbox,
    work_plane_normal,
)


def extract_all_features(shape, options: CadAnalyzeOptions) -> dict[str, Any]:
    bbox_tuple = shape_bbox(shape)
    wp_mode = options.work_plane.value if isinstance(options.work_plane, WorkPlane) else str(options.work_plane)
    wp_normal = work_plane_normal(wp_mode, bbox_tuple)

    polylines: list[dict] = []
    faces_out: list[dict] = []
    wires_out: list[dict] = []
    holes: list[dict] = []
    pockets: list[dict] = []
    ref_points: list[dict] = []
    contours: list[dict] = []
    contour_idx = 0

    for face_idx, face in enumerate(iterate_faces(shape)):
        fid = f"face_{face_idx}"
        payload, contour_idx = _extract_face_payload(
            face,
            fid=fid,
            options=options,
            wp_normal=wp_normal,
            contour_index_start=contour_idx,
        )
        polylines.extend(payload["polylines"])
        wires_out.extend(payload["wires"])
        contours.extend(payload["contours"])
        holes.extend(payload["holes"])
        ref_points.extend(payload["reference_points"])
        faces_out.append(payload["face"])

    outer_contour_ids = _select_global_outer_contours(contours)

    # BBox datums
    xmin, ymin, zmin, xmax, ymax, zmax = bbox_tuple
    cx, cy, cz = (xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2
    for label, pos in [
        ("bbox_center", (cx, cy, cz)),
        ("bbox_min", (xmin, ymin, zmin)),
        ("bbox_max", (xmax, ymax, zmax)),
    ]:
        ref_points.append({"id": f"pt_{label}", "kind": "datum", "position": _pt(pos), "meta": {}})

    solid_count = sum(1 for _ in _explorer(shape, TopAbs_SOLID))
    edge_count = sum(1 for _ in _explorer(shape, TopAbs_EDGE))
    summary = {
        "volume": _shape_volume(shape),
        "surface_area": _shape_surface_area(shape),
        "bbox": _bbox_model(bbox_tuple),
        "face_count": len(faces_out),
        "edge_count": edge_count,
        "solid_count": max(solid_count, 1),
    }

    return {
        "summary": summary,
        "reference_points": ref_points,
        "polylines": polylines,
        "faces": faces_out,
        "wires": wires_out,
        "contours": contours,
        "outer_contours": outer_contour_ids,
        "holes": _dedupe_holes(holes),
        "pockets": pockets,
        "work_plane": wp_mode,
        "work_plane_normal": _vec(wp_normal),
    }


def extract_face_features(shape, options: CadAnalyzeOptions, *, face_id: str) -> dict[str, Any]:
    """Extract contour/hole features for one selected face only."""
    bbox_tuple = shape_bbox(shape)
    wp_mode = options.work_plane.value if isinstance(options.work_plane, WorkPlane) else str(options.work_plane)
    wp_normal = work_plane_normal(wp_mode, bbox_tuple)

    target_index = _parse_face_index(face_id)
    selected_face = None
    for idx, face in enumerate(iterate_faces(shape)):
        if idx == target_index:
            selected_face = face
            break

    if selected_face is None:
        raise ValueError(f"face_id 不存在: {face_id}")

    canonical_face_id = f"face_{target_index}"
    payload, _ = _extract_face_payload(
        selected_face,
        fid=canonical_face_id,
        options=options,
        wp_normal=wp_normal,
        contour_index_start=0,
    )

    contours = payload["contours"]
    holes = _dedupe_holes(payload["holes"])
    wires = payload["wires"]
    outer_contours = _select_global_outer_contours(contours)

    return {
        "schema_version": "1.0",
        "unit": "mm",
        "target_face_id": canonical_face_id,
        "model_bbox": _bbox_model(bbox_tuple),
        "face": payload["face"],
        "reference_points": payload["reference_points"],
        "polylines": payload["polylines"],
        "wires": wires,
        "contours": contours,
        "outer_contours": outer_contours,
        "holes": holes,
        "pockets": [],
        "feature_groups": _build_feature_groups(contours=contours, holes=holes, wires=wires),
        "work_plane": wp_mode,
        "work_plane_normal": _vec(wp_normal),
    }


def _extract_face_payload(
    face,
    *,
    fid: str,
    options: CadAnalyzeOptions,
    wp_normal: tuple[float, float, float],
    contour_index_start: int,
) -> tuple[dict[str, Any], int]:
    surf = face_surface_info(face)
    area = face_area(face)
    wires = face_wires(face)

    polylines: list[dict] = []
    wires_out: list[dict] = []
    contours: list[dict] = []
    holes: list[dict] = []
    ref_points: list[dict] = []

    wire_infos: list[dict] = []
    surface_type = surf.get("surface_type")
    is_planar_face = surface_type == "plane"
    closure_tol = _wire_close_tol(options.linear_deflection)
    face_normal = _face_reference_normal(surf, wp_normal)

    for wi, wire in enumerate(wires):
        wid = f"wire_{fid}_{wi}"
        loc = wire_location_on_face(face, wire)
        pts = wire_to_polyline(
            wire,
            options.linear_deflection,
            options.angular_deflection,
            location=loc,
        )
        pid = f"poly_{wid}"
        closed = len(pts) >= 3 and _closed(pts, tol=closure_tol)
        polylines.append({"id": pid, "closed": closed, "points": [_pt(p) for p in pts]})

        wlen = wire_length(wire)
        warea = None
        if is_planar_face and closed and len(pts) >= 3:
            w2d = [_pt2d(project_point(p, face_normal)) for p in pts]
            warea = abs(_polygon_area_2d(w2d))

        wire_infos.append(
            {
                "id": wid,
                "length": wlen,
                "area": warea,
                "polyline_id": pid,
                "pts": pts,
                "closed": closed,
            }
        )

    if not wire_infos:
        face_rec = _face_record(fid, surf, area, None, [])
        return (
            {
                "face": face_rec,
                "polylines": polylines,
                "wires": wires_out,
                "contours": contours,
                "holes": holes,
                "reference_points": ref_points,
            },
            contour_index_start,
        )

    outer_id, inner_ids = _select_outer_wire(wire_infos, is_planar_face)
    contour_idx = contour_index_start

    for w in wire_infos:
        is_outer_wire = w["id"] == outer_id
        contour = classify_wire_contour(
            w.get("pts") or [],
            face_normal=tuple(face_normal),
            is_outer=is_outer_wire,
            wire_id=w["id"],
            polyline_id=w["polyline_id"],
            face_id=fid,
            contour_index=contour_idx,
            prefer_pca_plane=not is_planar_face,
        )
        contour_idx += 1
        if w.get("area"):
            contour["area"] = w["area"]
        contours.append(contour)

        is_inner_feature_loop = (not is_outer_wire) and contour["contour_type"] in (
            "circle",
            "slot",
            "rectangle",
            "hexagon",
        )
        if is_inner_feature_loop:
            _contour_to_hole(contour, fid, holes, options, ref_points)

        wires_out.append(
            {
                "id": w["id"],
                "face_id": fid,
                "is_outer": is_outer_wire,
                "length": w["length"],
                "area": w["area"],
                "polyline_id": w["polyline_id"],
                "contour_id": contour["id"],
                "contour_type": contour["contour_type"],
            }
        )
        ref_points.append(
            {
                "id": f"pt_{contour['id']}_center",
                "kind": "contour_center",
                "position": contour["center"],
                "meta": {
                    "contour_id": contour["id"],
                    "contour_type": contour["contour_type"],
                    "face_id": fid,
                },
            }
        )

    if surf.get("center"):
        ref_points.append(
            {
                "id": f"pt_{fid}_center",
                "kind": "face_center",
                "position": _pt(surf["center"]),
                "meta": {"face_id": fid},
            }
        )

    if surface_type == "cylinder" and surf.get("radius"):
        contour_idx = _add_cylinder_hole(
            surf,
            fid,
            holes,
            options,
            ref_points,
            contours,
            polylines,
            contour_idx,
        )

    face_rec = _face_record(fid, surf, area, outer_id, inner_ids)
    return (
        {
            "face": face_rec,
            "polylines": polylines,
            "wires": wires_out,
            "contours": contours,
            "holes": holes,
            "reference_points": ref_points,
        },
        contour_idx,
    )


def _select_outer_wire(wire_infos: list[dict], is_planar_face: bool) -> tuple[str, list[str]]:
    if is_planar_face:
        ranked = sorted(
            [w for w in wire_infos if w["closed"] and w["area"]],
            key=lambda w: w["area"] or 0.0,
            reverse=True,
        )
        if ranked:
            return ranked[0]["id"], [w["id"] for w in ranked[1:]]
    outer_id = max(wire_infos, key=lambda w: w["length"])["id"]
    return outer_id, []


def _select_global_outer_contours(contours: list[dict]) -> list[str]:
    best_outer: tuple[float, str | None] = (0.0, None)
    best_outer_by_length: tuple[float, str | None] = (0.0, None)
    for contour in contours:
        if not contour.get("is_outer"):
            continue
        if contour.get("area") and contour["area"] > best_outer[0]:
            best_outer = (contour["area"], contour["id"])
        perimeter = contour.get("perimeter") or 0.0
        if perimeter > best_outer_by_length[0]:
            best_outer_by_length = (perimeter, contour["id"])
    if best_outer[1]:
        return [best_outer[1]]
    if best_outer_by_length[1]:
        return [best_outer_by_length[1]]
    return []


def _build_feature_groups(*, contours: list[dict], holes: list[dict], wires: list[dict]) -> dict[str, dict]:
    contours_by_type: dict[str, list[dict]] = {}
    for c in contours:
        contours_by_type.setdefault(c.get("contour_type", "unknown"), []).append(c)

    holes_by_type: dict[str, list[dict]] = {}
    for h in holes:
        holes_by_type.setdefault(h.get("contour_type") or h.get("kind") or "unknown", []).append(h)

    wires_by_role = {
        "outer": [w for w in wires if w.get("is_outer")],
        "inner": [w for w in wires if not w.get("is_outer")],
    }
    return {
        "contours_by_type": contours_by_type,
        "holes_by_type": holes_by_type,
        "wires_by_role": wires_by_role,
    }


def _shape_volume(shape) -> float | None:
    try:
        props = GProp_GProps()
        brepgprop.VolumeProperties(shape, props)
        return props.Mass()
    except Exception:
        return None


def _shape_surface_area(shape) -> float | None:
    try:
        props = GProp_GProps()
        brepgprop.SurfaceProperties(shape, props)
        return props.Mass()
    except Exception:
        return None


def _parse_face_index(face_id: str) -> int:
    raw = (face_id or "").strip()
    if not raw:
        raise ValueError("face_id 不能为空")
    if raw.isdigit():
        idx = int(raw)
        if idx < 0:
            raise ValueError(f"face_id 非法: {face_id}")
        return idx
    if raw.startswith("face_") and raw[5:].isdigit():
        idx = int(raw[5:])
        if idx < 0:
            raise ValueError(f"face_id 非法: {face_id}")
        return idx
    raise ValueError(f"face_id 格式无效: {face_id}（示例: face_12）")


def _add_cylinder_hole(
    surf,
    fid,
    holes,
    options,
    ref_points,
    contours: list,
    polylines: list,
    contour_idx: int,
) -> int:
    """圆柱面 → 孔 + 合成圆轮廓（顶面无内环时仍输出 circle contour）。

    注意：很多 STEP 会包含大量“外圆柱面/轴/圆角/倒角过渡面”，它们并不是孔。
    这里做两层过滤：
    1) 尺寸过滤（diameter_min/max）
    2) 仅在显式开启 options.include_cylinder_holes 时才输出（默认关闭）
    """

    # 默认不输出圆柱面“孔”（避免远处/多余圆大量出现）
    if not getattr(options, "include_cylinder_holes", False):
        return contour_idx

    radius = surf.get("radius") or 0.0
    diam = radius * 2.0
    if not (options.hole_diameter_min <= diam <= options.hole_diameter_max):
        return contour_idx
    center = surf.get("center", (0.0, 0.0, 0.0))
    axis = surf.get("axis", (0.0, 0.0, 1.0))
    pts = _discretize_circle_3d(center, axis, radius)
    pid = f"poly_hole_cyl_{fid}"
    polylines.append({"id": pid, "closed": True, "points": [_pt(p) for p in pts]})
    contour = classify_wire_contour(
        pts,
        face_normal=tuple(axis),
        is_outer=False,
        wire_id=None,
        polyline_id=pid,
        face_id=fid,
        contour_index=contour_idx,
    )
    contour_idx += 1
    contours.append(contour)
    cid = contour["id"]
    holes.append(
        {
            "id": f"hole_cyl_{fid}",
            "kind": "circle",
            "contour_type": "circle",
            "center": _pt(center),
            "axis": _vec(axis),
            "diameter": diam,
            "depth": None,
            "face_id": fid,
            "wire_id": None,
            "cylindrical_face_ids": [fid],
            "parameters": {"diameter": diam, "length": None, "width": None, "across_flats": None},
        }
    )
    ref_points.append(
        {
            "id": f"pt_hole_{fid}",
            "kind": "hole_center",
            "position": _pt(center),
            "meta": {"diameter": diam, "contour_type": "circle", "contour_id": cid},
        }
    )
    ref_points.append(
        {
            "id": f"pt_{cid}_center",
            "kind": "contour_center",
            "position": contour["center"],
            "meta": {"contour_id": cid, "contour_type": "circle", "face_id": fid},
        }
    )
    return contour_idx


def _discretize_circle_3d(
    center: tuple[float, float, float],
    axis: tuple[float, float, float],
    radius: float,
    segments: int = 48,
) -> list[tuple[float, float, float]]:
    ax = _normalize(axis)
    ref = (1.0, 0.0, 0.0) if abs(ax[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _cross(ax, ref)
    u = _normalize(u)
    v = _normalize(_cross(ax, u))
    cx, cy, cz = center
    pts: list[tuple[float, float, float]] = []
    for i in range(segments + 1):
        t = 2.0 * math.pi * i / segments
        pts.append(
            (
                cx + radius * (math.cos(t) * u[0] + math.sin(t) * v[0]),
                cy + radius * (math.cos(t) * u[1] + math.sin(t) * v[1]),
                cz + radius * (math.cos(t) * u[2] + math.sin(t) * v[2]),
            )
        )
    return pts


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    L = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / L, v[1] / L, v[2] / L)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _contour_to_hole(contour: dict, face_id: str, holes: list, options, ref_points: list | None = None) -> None:
    ctype = contour["contour_type"]
    params = contour.get("parameters") or {}
    diam = params.get("diameter")
    if ctype == "circle" and diam is not None:
        if not (options.hole_diameter_min <= diam <= options.hole_diameter_max):
            return
    holes.append(
        {
            "id": f"hole_{contour['id']}",
            "kind": ctype,
            "contour_type": ctype,
            "center": contour["center"],
            "axis": contour["normal"],
            "diameter": diam,
            "depth": None,
            "face_id": face_id,
            "wire_id": contour.get("wire_id"),
            "cylindrical_face_ids": [],
            "parameters": {
                "diameter": params.get("diameter"),
                "length": params.get("length"),
                "width": params.get("width"),
                "across_flats": params.get("across_flats"),
            },
        }
    )
    if ref_points is not None:
        ref_points.append(
            {
                "id": f"pt_hole_{contour['id']}",
                "kind": "hole_center",
                "position": contour["center"],
                "meta": {
                    "diameter": diam,
                    "contour_type": ctype,
                    "contour_id": contour["id"],
                    "face_id": face_id,
                },
            }
        )


def _dedupe_holes(holes: list[dict]) -> list[dict]:
    seen: list[tuple[float, float, float]] = []
    out = []
    for h in holes:
        c = h["center"]
        key = (round(c["x"], 2), round(c["y"], 2), round(c["z"], 2))
        if any(_dist3(key, s) < 1.0 for s in seen):
            continue
        seen.append(key)
        out.append(h)
    return out


def _face_record(fid, surf, area, outer_id, inner_ids):
    return {
        "id": fid,
        "surface_type": surf.get("surface_type", "other"),
        "area": area,
        "normal": _vec(surf["normal"]) if surf.get("normal") else None,
        "axis": _vec(surf["axis"]) if surf.get("axis") else None,
        "center": _pt(surf["center"]) if surf.get("center") else None,
        "radius": surf.get("radius"),
        "bbox": None,
        "outer_wire_id": outer_id,
        "inner_wire_ids": inner_ids,
    }


def _explorer(shape, kind):
    exp = TopExp_Explorer(shape, kind)
    while exp.More():
        yield exp.Current()
        exp.Next()


def _closed(pts, tol=1e-2) -> bool:
    return _dist3(pts[0], pts[-1]) < tol


def _wire_close_tol(linear_deflection: float) -> float:
    """Closure tolerance tied to discretization granularity."""
    return max(1e-3, linear_deflection)


def _face_reference_normal(surf: dict, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    """Best available normal for contour projection on this face."""
    n = surf.get("normal")
    if n:
        return tuple(n)
    axis = surf.get("axis")
    if axis:
        return tuple(axis)
    return tuple(fallback)


def _dist3(a, b) -> float:
    if isinstance(a, dict):
        a = (a["x"], a["y"], a["z"])
    if isinstance(b, dict):
        b = (b["x"], b["y"], b["z"])
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _polygon_area_2d(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def _pt(t) -> dict:
    return {"x": float(t[0]), "y": float(t[1]), "z": float(t[2])}


def _pt2d(t) -> tuple[float, float]:
    return (float(t[0]), float(t[1]))


def _vec(t) -> dict:
    return {"x": float(t[0]), "y": float(t[1]), "z": float(t[2])}


def _bbox_model(b) -> dict:
    xmin, ymin, zmin, xmax, ymax, zmax = b
    return {
        "xmin": xmin,
        "ymin": ymin,
        "zmin": zmin,
        "xmax": xmax,
        "ymax": ymax,
        "zmax": zmax,
        "center": _pt(((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)),
    }
