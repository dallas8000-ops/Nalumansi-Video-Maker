import pytest
from pydantic import ValidationError

from app.models import AudioSettings, GenerationRequest


def test_generation_request_contains_showcase_prompt_and_audio_settings():
    request = GenerationRequest(
        aspect_ratio="9:16",
        duration_seconds=10,
        outfit_asset_id="outfit-1",
        background_asset_id="background-1",
        audio=AudioSettings(
            music_asset_id="music-1",
            music_start_seconds=2,
            music_volume=0.7,
            original_audio_volume=0.2,
            mute_original_audio=False,
        ),
    )

    assert "walks slowly toward the camera" in request.prompt
    assert request.audio.music_start_seconds == 2
    assert request.audio.music_volume == 0.7


def test_generation_request_rejects_duration_outside_supported_range():
    with pytest.raises(ValidationError):
        GenerationRequest(
            aspect_ratio="9:16",
            duration_seconds=20,
            outfit_asset_id="outfit-1",
            background_asset_id="background-1",
        )
