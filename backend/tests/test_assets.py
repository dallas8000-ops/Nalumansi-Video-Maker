from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app


def test_upload_asset_returns_generated_asset_id():
    client = TestClient(app)

    response = client.post(
        "/api/assets",
        data={"kind": "background"},
        files={"file": ("lobby.png", BytesIO(b"fake-image"), "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "background"
    assert body["asset_id"]
    assert body["filename"].endswith(".png")
    assert body["url"].startswith("http://127.0.0.1:8000/api/assets/")


def test_upload_music_asset_returns_generated_asset_id():
    client = TestClient(app)

    response = client.post(
        "/api/assets",
        data={"kind": "music"},
        files={"file": ("track.mp3", BytesIO(b"fake-audio"), "audio/mpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "music"
    assert body["filename"].endswith(".mp3")


def test_uploaded_asset_can_be_retrieved_by_id():
    client = TestClient(app)

    upload = client.post(
        "/api/assets",
        data={"kind": "background"},
        files={"file": ("lobby.png", BytesIO(b"fake-image"), "image/png")},
    )
    asset_id = upload.json()["asset_id"]

    response = client.get(f"/api/assets/{asset_id}")

    assert response.status_code == 200
    assert response.content == b"fake-image"
