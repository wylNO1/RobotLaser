"""Unit tests for 2D contour classification."""

from __future__ import annotations

import math

import pytest

from app.occ.features.contour_classifier import classify_wire_contour


def _circle_pts_3d(r: float, n: int = 48, z: float = 0.0):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        pts.append((r * math.cos(t), r * math.sin(t), z))
    pts.append(pts[0])
    return pts


def _rect_pts_3d(lx: float, ly: float, z: float = 0.0):
    x0, y0 = -lx / 2, -ly / 2
    return [
        (x0, y0, z),
        (x0 + lx, y0, z),
        (x0 + lx, y0 + ly, z),
        (x0, y0 + ly, z),
        (x0, y0, z),
    ]


def _slot_pts_3d(length: float, width: float, z: float = 0.0):
    return _rect_pts_3d(length, width, z)


def test_classify_circle():
    pts = _circle_pts_3d(15)
    c = classify_wire_contour(
        pts,
        face_normal=(0, 0, 1),
        is_outer=False,
        wire_id="w1",
        polyline_id="p1",
        face_id="f1",
        contour_index=0,
    )
    assert c["contour_type"] == "circle"
    assert c["parameters"]["diameter"] == pytest.approx(30, rel=0.15)


def test_classify_rectangle():
    pts = _rect_pts_3d(30, 20)
    c = classify_wire_contour(
        pts,
        face_normal=(0, 0, 1),
        is_outer=False,
        wire_id="w1",
        polyline_id="p1",
        face_id="f1",
        contour_index=0,
    )
    assert c["contour_type"] == "rectangle"
    assert c["parameters"]["length"] == pytest.approx(30, rel=0.2)
    assert c["parameters"]["width"] == pytest.approx(20, rel=0.2)


def test_classify_slot():
    pts = _slot_pts_3d(50, 10)
    c = classify_wire_contour(
        pts,
        face_normal=(0, 0, 1),
        is_outer=False,
        wire_id="w1",
        polyline_id="p1",
        face_id="f1",
        contour_index=0,
    )
    assert c["contour_type"] == "slot"
    assert c["parameters"]["length"] >= c["parameters"]["width"]


def test_classify_outer():
    pts = _rect_pts_3d(100, 60)
    c = classify_wire_contour(
        pts,
        face_normal=(0, 0, 1),
        is_outer=True,
        wire_id="w0",
        polyline_id="p0",
        face_id="f0",
        contour_index=0,
    )
    assert c["contour_type"] == "outer"
    assert c["is_outer"] is True
