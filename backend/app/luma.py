from typing import Any, Literal

import httpx
from lumaai import LumaAI

# A keyframe is either a fresh image ("image", url) or a continuation of a
# previously *completed* generation ("generation", generation_id) — Luma's
# "extend" mechanic. See build_generation_payload().
KeyframeSource = tuple[Literal["image", "generation"], str]

TERMINAL_STATES = {"completed", "failed"}


class LumaClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None):
        self._client = LumaAI(auth_token=api_key, http_client=http_client)

    def create_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        generation = self._client.generations.create(**payload)
        if not generation.id:
            raise ValueError("Luma response did not include a generation id")
        return _serialize(generation)

    def get_generation(self, generation_id: str) -> dict[str, Any]:
        generation = self._client.generations.get(generation_id)
        return _serialize(generation)


def _serialize(generation: Any) -> dict[str, Any]:
    return {
        "provider_id": generation.id,
        "status": generation.state or "queued",
        "video_url": generation.assets.video if generation.assets else None,
        "failure_reason": generation.failure_reason,
    }


def _keyframe(source: KeyframeSource) -> dict[str, Any]:
    kind, value = source
    if kind == "image":
        return {"type": "image", "url": value}
    if kind == "generation":
        return {"type": "generation", "id": value}
    raise ValueError(f"unknown keyframe source kind: {kind!r}")


def build_generation_payload(
    *,
    prompt: str,
    frame0: KeyframeSource,
    frame1: KeyframeSource,
    aspect_ratio: str,
    duration_seconds: int,
) -> dict[str, Any]:
    """Luma's video model takes exactly two keyframe slots per call (frame0,
    frame1). frame0 is either a plain reference image or, per Luma's "extend"
    mechanic, {"type": "generation", "id": <a COMPLETED prior generation's id>}
    to continue seamlessly from that clip's last frame — this is how multiple
    outfit images become one continuous multi-shot video instead of one call
    with N images (the API has no such call)."""
    return {
        "model": "ray-2",
        "generation_type": "video",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": f"{duration_seconds}s",
        "keyframes": {
            "frame0": _keyframe(frame0),
            "frame1": _keyframe(frame1),
        },
    }
