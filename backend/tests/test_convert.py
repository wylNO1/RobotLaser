from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_urdf_convert_multipart() -> None:
    urdf_path = Path(__file__).resolve().parents[2] / "examples" / "minimal_robot.urdf"
    data = urdf_path.read_bytes()
    r = client.post(
        "/api/v1/urdf/convert",
        files={"file": ("minimal_robot.urdf", data, "application/xml")},
        data={"embed_meshes": "true"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["robot_name"] == "minimal"
