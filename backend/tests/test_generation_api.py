import subprocess
from pathlib import Path

import imageio_ffmpeg
import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.models import AudioSettings


FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _make_clip(path: Path, seconds: float = 0.4, with_audio: bool = False) -> Path:
    args = [FFMPEG, "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=64x64:rate=10"]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    args += ["-pix_fmt", "yuv420p"]
    if with_audio:
        args += ["-c:a", "aac", "-shortest"]
    args += [str(path)]
    subprocess.run(args, check=True, capture_output=True)
    return path


class FakeLumaClient:
    """Stands in for LumaClient so tests never touch the network. Each
    create_generation call gets its own incrementing provider id; get_generation
    reports it as immediately completed unless the test configures otherwise."""

    responses: dict[str, dict] = {}

    def __init__(self, *args, **kwargs):
        self.created = 0

    def create_generation(self, payload):
        self.created += 1
        return {"provider_id": f"gen-{self.created}", "status": "queued", "video_url": None, "failure_reason": None}

    def get_generation(self, provider_id):
        return FakeLumaClient.responses.get(
            provider_id,
            {"provider_id": provider_id, "status": "completed", "video_url": "https://example.test/segment.mp4", "failure_reason": None},
        )


@pytest.fixture(autouse=True)
def _reset_fake_luma_responses():
    FakeLumaClient.responses = {}
    yield
    FakeLumaClient.responses = {}


@pytest.fixture
def fast_polling(monkeypatch):
    # keep any timeout-path test from actually sleeping in real time
    monkeypatch.setattr(main_module, "POLL_INTERVAL_SECONDS", 0)


def test_generation_endpoint_chains_one_call_per_outfit_and_returns_completed_video(monkeypatch, tmp_path, fast_polling):
    monkeypatch.setattr(main_module, "LumaClient", FakeLumaClient)
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main_module, "_download_video", lambda destination, video_url: _make_clip(destination))

    client = TestClient(app)
    response = client.post(
        "/api/generations",
        json={
            "aspect_ratio": "9:16",
            "duration_seconds": 5,
            "outfit_asset_ids": ["outfit-1", "outfit-2", "outfit-3"],
            "background_asset_id": "background-1",
        },
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    final = client.get(f"/api/generations/{job_id}").json()
    assert final["status"] == "completed", final
    assert final["total_steps"] == 3
    assert final["provider_ids"] == ["gen-1", "gen-2", "gen-3"]
    assert final["video_url"] == f"http://127.0.0.1:8000/api/videos/{job_id}.mp4"
    assert (tmp_path / f"{job_id}.mp4").is_file()
    # intermediate segment files are cleaned up once assembled
    assert not list(tmp_path.glob(f"{job_id}-segment-*.mp4"))


def test_generation_endpoint_stops_chain_on_first_failed_segment(monkeypatch, tmp_path, fast_polling):
    monkeypatch.setattr(main_module, "LumaClient", FakeLumaClient)
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main_module, "_download_video", lambda destination, video_url: _make_clip(destination))
    FakeLumaClient.responses["gen-2"] = {
        "provider_id": "gen-2",
        "status": "failed",
        "video_url": None,
        "failure_reason": "provider rejected the request",
    }

    client = TestClient(app)
    response = client.post(
        "/api/generations",
        json={
            "aspect_ratio": "9:16",
            "duration_seconds": 5,
            "outfit_asset_ids": ["outfit-1", "outfit-2", "outfit-3"],
            "background_asset_id": "background-1",
        },
    )
    job_id = response.json()["job_id"]

    final = client.get(f"/api/generations/{job_id}").json()
    assert final["status"] == "failed"
    assert final["error"] == "provider rejected the request"
    # the third outfit was never attempted once the second segment failed
    assert final["provider_ids"] == ["gen-1", "gen-2"]


def test_generation_endpoint_fails_job_when_luma_never_reaches_a_terminal_state(monkeypatch, tmp_path, fast_polling):
    monkeypatch.setattr(main_module, "LumaClient", FakeLumaClient)
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main_module, "POLL_TIMEOUT_SECONDS", 0)
    FakeLumaClient.responses["gen-1"] = {"provider_id": "gen-1", "status": "dreaming", "video_url": None, "failure_reason": None}

    client = TestClient(app)
    response = client.post(
        "/api/generations",
        json={"aspect_ratio": "9:16", "duration_seconds": 5, "outfit_asset_id": "outfit-1", "background_asset_id": "background-1"},
    )
    job_id = response.json()["job_id"]

    final = client.get(f"/api/generations/{job_id}").json()
    assert final["status"] == "failed"
    assert "timed out" in final["error"]


def test_generation_status_returns_not_found_for_unknown_job():
    client = TestClient(app)
    response = client.get("/api/generations/unknown-job")
    assert response.status_code == 404


def test_generation_endpoint_rejects_missing_music_asset(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "LumaClient", FakeLumaClient)
    monkeypatch.setattr(main_module, "UPLOAD_DIR", tmp_path)

    client = TestClient(app)
    response = client.post(
        "/api/generations",
        json={
            "aspect_ratio": "9:16",
            "duration_seconds": 5,
            "outfit_asset_id": "outfit-1",
            "background_asset_id": "background-1",
            "audio": {"music_asset_id": "does-not-exist"},
        },
    )
    assert response.status_code == 422


# --- video assembly (real ffmpeg, synthetic fixtures, no network) ---


def test_concatenate_segments_sums_durations(tmp_path):
    clip_a = _make_clip(tmp_path / "a.mp4", seconds=0.5)
    clip_b = _make_clip(tmp_path / "b.mp4", seconds=0.5)
    destination = tmp_path / "out.mp4"

    main_module._concatenate_segments(FFMPEG, [clip_a, clip_b], destination)

    assert destination.is_file()
    probe = subprocess.run([FFMPEG, "-i", str(destination)], capture_output=True, text=True)
    assert "Duration: 00:00:00.9" in probe.stderr or "Duration: 00:00:01.0" in probe.stderr


def test_mux_audio_with_muted_original_uses_only_music_track(tmp_path):
    video = _make_clip(tmp_path / "video.mp4", seconds=0.5, with_audio=True)
    music = _make_clip(tmp_path / "music_source.mp4", seconds=0.5, with_audio=True)
    music_audio_only = tmp_path / "music.aac"
    subprocess.run([FFMPEG, "-y", "-i", str(music), "-vn", "-c:a", "aac", str(music_audio_only)], check=True, capture_output=True)
    destination = tmp_path / "final.mp4"

    main_module._mux_audio(FFMPEG, video, music_audio_only, AudioSettings(mute_original_audio=True), destination)

    assert destination.is_file()
    assert main_module._has_audio_stream(FFMPEG, destination)


def test_mux_audio_with_no_music_and_no_mute_leaves_video_untouched(tmp_path):
    video = _make_clip(tmp_path / "video.mp4", seconds=0.5, with_audio=True)
    destination = tmp_path / "final.mp4"

    main_module._mux_audio(FFMPEG, video, None, AudioSettings(), destination)

    assert destination.is_file()
    assert not video.exists()  # replaced (moved) into destination, not copied
