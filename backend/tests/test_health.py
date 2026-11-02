from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_error_shape():
    response = TestClient(create_app()).get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
