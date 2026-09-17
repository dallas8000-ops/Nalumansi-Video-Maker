from typing import Literal

from pydantic import BaseModel, Field


SHOWCASE_PROMPT = (
    "An elegant fashion showcase in a professional showroom. "
    "The model walks slowly toward the camera, turns slightly to show the outfit, "
    "with natural fabric movement and refined showroom lighting. No extra accessories."
)


class AudioSettings(BaseModel):
    music_asset_id: str | None = None
    music_start_seconds: float = Field(default=0, ge=0)
    music_volume: float = Field(default=1, ge=0, le=1)
    original_audio_volume: float = Field(default=1, ge=0, le=1)
    mute_original_audio: bool = False


class GenerationRequest(BaseModel):
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    duration_seconds: Literal[5] = 5  # ray-3.2 rejects 10s whenever start_frame/end_frame are both set (confirmed via direct API test) — this app always sets both, so 5 is the only valid value
    outfit_asset_id: str | None = None
    outfit_asset_ids: list[str] = Field(default_factory=list)
    background_asset_id: str
    prompt: str = SHOWCASE_PROMPT
    audio: AudioSettings = Field(default_factory=AudioSettings)
