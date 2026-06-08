"""GLB container format tests (JSON chunk length / padding)."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from app.services.stp_converter import stp_bytes_to_glb
from app.utils.occ_guard import occ_installed
from app.utils.raw_glb import validate_glb_bytes

pytestmark = pytest.mark.skipif(not occ_installed(), reason="pythonOCC not installed")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cad" / "box_100x60x20.step"


def test_glb_json_chunk_length_matches_content():
    glb = stp_bytes_to_glb(FIXTURE.read_bytes(), FIXTURE.name)
    validate_glb_bytes(glb)

    json_len = struct.unpack("<I", glb[12:16])[0]
    json_chunk = glb[20 : 20 + json_len]
    assert len(json_chunk) == json_len

    # Three.js style: parse exactly json_len bytes (padding = spaces only)
    text = json_chunk.decode("utf-8")
    assert "\x00" not in text, "JSON chunk must not contain NUL padding"
    doc = json.loads(text.rstrip())
    assert "meshes" in doc and doc["meshes"][0]["primitives"]


def test_glb_total_file_length():
    glb = stp_bytes_to_glb(FIXTURE.read_bytes(), FIXTURE.name)
    total = struct.unpack("<I", glb[8:12])[0]
    assert total == len(glb)
