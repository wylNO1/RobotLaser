from __future__ import annotations

from pathlib import Path

from app.services.metadata import extract_robot_meta
from app.services.skeleton_builder import parse_urdf_to_babylon_scene
from app.services.urdf_parser import MeshResolver, parse_urdf_xml


def _minimal_urdf() -> str:
    p = Path(__file__).resolve().parents[2] / "examples" / "minimal_robot.urdf"
    return p.read_text(encoding="utf-8")


def test_parse_urdf_xml() -> None:
    parsed = parse_urdf_xml(_minimal_urdf())
    assert parsed.robot_name == "minimal"
    assert "base_link" in parsed.links
    assert len(parsed.joints_raw) == 1
    assert parsed.joints_raw[0]["name"] == "shoulder"


def test_extract_robot_meta() -> None:
    parsed = parse_urdf_xml(_minimal_urdf())
    meta = extract_robot_meta(parsed)
    assert meta["format"] == "robot_meta"
    assert "arm_link" in meta["links"]


def test_babylon_scene_minimal() -> None:
    xml = _minimal_urdf()
    scene = parse_urdf_to_babylon_scene(xml, MeshResolver(Path(".")), embed_meshes=True)
    assert scene["format"] == "babylon_robot_scene"
    assert scene["root_link"] == "base_link"
    assert any(l["name"] == "arm_link" for l in scene["links"])
