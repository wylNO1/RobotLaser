"""CAD API tests (no pythonOCC required for status)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cad_status():
    r = client.get("/api/v1/cad/status")
    assert r.status_code == 200
    body = r.json()
    assert "pythonocc_available" in body
    assert body["api_version"] == "1.0"
