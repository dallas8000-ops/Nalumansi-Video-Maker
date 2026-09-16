from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app


def test_generation_endpoint_queues_video_request(monkeypatch):
    monkeypatch.setattr(
        main_module.LumaClient,
        "create_generation",
        lambda self, payload: {"provider_id": "provider-job-1", "status": "queued"},
    )
    client = TestClient(app)

    response = client.post(
        "/api/generations",
        json={
            "aspect_ratio": "9:16",
            "duration_seconds": 8,
            "outfit_asset_id": "outfit-1",
            "background_asset_id": "background-1",
            "audio": {
                "music_asset_id": "music-1",
                "music_start_seconds": 0,
                "music_volume": 0.8,
                "original_audio_volume": 0.2,
                "mute_original_audio": False,
            },
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]

    status_response = client.get(f"/api/generations/{body['job_id']}")

    assert status_response.status_code == 200
    assert status_response.json() == {
        "job_id": body["job_id"],
        "status": "queued",
        "provider_id": "provider-job-1",
    }


def test_generation_status_returns_not_found_for_unknown_job():
    client = TestClient(app)

    response = client.get("/api/generations/unknown-job")

    assert response.status_code == 404
