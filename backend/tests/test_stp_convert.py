"""STEP → GLB API tests."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.occ_guard import occ_installed
from app.utils.raw_glb import validate_glb_bytes

pytestmark = pytest.mark.skipif(not occ_installed(), reason="pythonOCC not installed")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cad" / "box_100x60x20.step"


def test_stp_convert_ascii_filename():
    client = TestClient(app)
    data = FIXTURE.read_bytes()
    r = client.post(
        "/api/v1/stp/convert",
        files={"file": ("box_100x60x20.step", data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "model/gltf-binary"
    assert len(r.content) > 100


def test_convert_skips_cascadio_check_when_occ_present(monkeypatch):
    """Regression: calling cascadio_installed() before OCC caused 0xC06D007F."""
    calls: list[str] = []

    def _track():
        calls.append("cascadio_installed")
        return True

    monkeypatch.setattr("app.routers.stp.cascadio_installed", _track)
    client = TestClient(app)
    data = FIXTURE.read_bytes()
    r = client.post(
        "/api/v1/stp/convert",
        files={"file": ("box.stp", data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    assert calls == []


def _glb_json(glb: bytes) -> dict:
    validate_glb_bytes(glb)
    json_len = struct.unpack("<I", glb[12:16])[0]
    return json.loads(glb[20 : 20 + json_len].rstrip(b" ").decode("utf-8"))


def test_stp_face_index_returns_dynamic_face_list():
    """GLB 应按面拆分节点，scene.extras 含 face_ids 供 Babylon 拾取。"""
    client = TestClient(app)
    data = FIXTURE.read_bytes()
    r = client.post(
        "/api/v1/stp/convert",
        files={"file": ("box_100x60x20.step", data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    doc = _glb_json(r.content)
    cad = doc["scenes"][0].get("extras", {}).get("cad", {})
    face_ids = cad.get("face_ids") or []
    assert len(face_ids) == 6
    assert face_ids[0] == "face_0"

    face_nodes = [n for n in doc["nodes"] if (n.get("name") or "").startswith("face_")]
    assert len(face_nodes) == 6
    for n in face_nodes:
        extras = n.get("extras", {}).get("cad", {})
        assert extras.get("role") == "face"
        assert extras.get("face_id") == n["name"]
        assert "mesh" in n

    wire_nodes = [n for n in doc["nodes"] if (n.get("name") or "").startswith("wire_face_")]
    assert len(wire_nodes) >= 6
    assert len(doc["meshes"]) >= 12


def test_stp_part_pick_level():
    """pick_level=part 时每个 Solid 为独立 mesh 节点（PythonProject2 行为）。"""
    client = TestClient(app)
    data = FIXTURE.read_bytes()
    r = client.post(
        "/api/v1/stp/convert?pick_level=part",
        files={"file": ("box_100x60x20.step", data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    doc = _glb_json(r.content)
    part_nodes = [n for n in doc["nodes"] if n.get("mesh") is not None]
    assert len(part_nodes) >= 1
    assert part_nodes[0].get("name", "").startswith("Part_")


def test_stp_convert_chinese_filename_no_500():
    """中文文件名不得触发 Content-Disposition latin-1 编码 500。"""
    client = TestClient(app)
    data = FIXTURE.read_bytes()
    r = client.post(
        "/api/v1/stp/convert",
        files={"file": ("零件.step", data, "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    assert "filename*=" in r.headers.get("content-disposition", "")
