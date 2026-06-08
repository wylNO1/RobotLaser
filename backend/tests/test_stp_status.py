from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stp_status():
    r = client.get("/api/v1/stp/status")
    assert r.status_code == 200
    body = r.json()
    assert "convert_ready" in body
