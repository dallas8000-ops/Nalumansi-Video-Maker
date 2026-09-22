from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import security as security_module
from app.security import require_api_key


def _protected_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    def protected() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_require_api_key_is_a_no_op_when_no_key_is_configured(monkeypatch):
    # Matches the current deployment: APP_API_KEY unset means every endpoint
    # stays open, exactly as it behaves today with no auth at all.
    monkeypatch.setattr(security_module._settings, "app_api_key", None)
    client = TestClient(_protected_app())

    response = client.get("/protected")

    assert response.status_code == 200


def test_require_api_key_rejects_missing_header_once_a_key_is_configured(monkeypatch):
    monkeypatch.setattr(security_module._settings, "app_api_key", "secret-value")
    client = TestClient(_protected_app())

    response = client.get("/protected")

    assert response.status_code == 401


def test_require_api_key_rejects_wrong_header_value(monkeypatch):
    monkeypatch.setattr(security_module._settings, "app_api_key", "secret-value")
    client = TestClient(_protected_app())

    response = client.get("/protected", headers={"X-API-Key": "wrong-value"})

    assert response.status_code == 401


def test_require_api_key_accepts_matching_header_value(monkeypatch):
    monkeypatch.setattr(security_module._settings, "app_api_key", "secret-value")
    client = TestClient(_protected_app())

    response = client.get("/protected", headers={"X-API-Key": "secret-value"})

    assert response.status_code == 200
