"""ikfast API 测试（无 DLL 时仅测 status 与校验）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ikfast.native_loader import ikfast_available
from app.main import app

client = TestClient(app)


def test_ikfast_status() -> None:
    r = client.get("/api/v1/ikfast/status")
    assert r.status_code == 200
    data = r.json()
    assert "ikfast_available" in data
    assert data["ikfast_available"] == ikfast_available()
    assert any(m["model_id"] == "m20ia_35m" for m in data["models"])


def test_inverse_without_library() -> None:
    if ikfast_available():
        pytest.skip("已安装 DLL，跳过 501 测试")
    r = client.post(
        "/api/v1/ikfast/m20ia-35m/inverse",
        json={
            "position": {"x": 0.5, "y": 0.0, "z": 0.8},
            "rpy": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
        },
    )
    assert r.status_code == 501


def test_inverse_validation_both_rotation_and_rpy() -> None:
    r = client.post(
        "/api/v1/ikfast/m20ia-35m/inverse",
        json={
            "position": {"x": 0, "y": 0, "z": 0},
            "rpy": {"roll": 0, "pitch": 0, "yaw": 0},
            "rotation": {
                "r00": 1, "r01": 0, "r02": 0,
                "r10": 0, "r11": 1, "r12": 0,
                "r20": 0, "r21": 0, "r22": 1,
            },
        },
    )
    if ikfast_available():
        assert r.status_code == 422
    else:
        assert r.status_code in (422, 501)


@pytest.mark.skipif(not ikfast_available(), reason="需要已编译的 m20ia_35m_ik.dll")
def test_forward_roundtrip() -> None:
    joints = [0.0, -0.5, 0.3, 0.0, 1.0, 0.0]
    fk = client.post("/api/v1/ikfast/m20ia-35m/forward", json={"joints": joints})
    assert fk.status_code == 200
    pose = fk.json()
    ik = client.post(
        "/api/v1/ikfast/m20ia-35m/inverse",
        json={
            "position": pose["position"],
            "rotation": pose["rotation"],
        },
    )
    assert ik.status_code == 200
    assert ik.json()["num_solutions"] >= 1
