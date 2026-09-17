from typing import Any, Literal

import httpx
from lumaai import LumaAI

# A keyframe is either a fresh image ("image", url) or a continuation of a
# previously *completed* generation ("generation", generation_id) — Luma's
# "extend" mechanic. See build_generation_payload().
KeyframeSource = tuple[Literal["image", "generation"], str]

TERMINAL_STATES = {"completed", "failed"}

# A keyframe is either a fresh image ("image", url) or a continuation of a
# previously *completed* generation ("generation", generation_id) — ray-3.2's
# "extend" mechanic. See build_generation_payload().
KeyframeSource = tuple[Literal["image", "generation"], str]

TERMINAL_STATES = {"completed", "failed"}

# This project's Luma dashboard (Video generation card) grants exactly one
# video model: ray-3.2, served from the Agents API host below. The legacy
# Dream Machine host (api.lumalabs.ai/dream-machine/v1, model=ray-2) 403s for
# this key no matter what kind of key is generated — it isn't an entitlement
# a key can be upgraded into, it's a different product this project was never
# granted. Do not point this client back at Dream Machine without confirming
# the dashboard's "Video generation" card lists ray-2.
BASE_URL = "https://agents.lumalabs.ai/v1"


class LumaClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None):
        self._client = http_client or httpx.Client(timeout=30)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def create_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(f"{BASE_URL}/generations", json=payload, headers=self._headers)
        response.raise_for_status()
        body = response.json()
        if not body.get("id"):
            raise ValueError("Luma response did not include a generation id")
        return _serialize(body)

    def get_generation(self, generation_id: str) -> dict[str, Any]:
        response = self._client.get(f"{BASE_URL}/generations/{generation_id}", headers=self._headers)
        response.raise_for_status()
        return _serialize(response.json())


def _serialize(body: dict[str, Any]) -> dict[str, Any]:
    output = body.get("output") or []
    return {
        "provider_id": body.get("id"),
        "status": body.get("state") or "queued",
        "video_url": output[0]["url"] if output else None,
        "failure_reason": body.get("failure_reason"),
    }


def _keyframe(source: KeyframeSource) -> dict[str, Any]:
    kind, value = source
    if kind == "image":
        return {"url": value}
    if kind == "generation":
        return {"generation_id": value}
    raise ValueError(f"unknown keyframe source kind: {kind!r}")


def build_generation_payload(
    *,
    prompt: str,
    frame0: KeyframeSource,
    frame1: KeyframeSource,
    aspect_ratio: str,
    duration_seconds: int,
    resolution: str = "720p",
) -> dict[str, Any]:
    """ray-3.2 nests its video-specific fields under `video` and calls its two
    keyframe slots start_frame/end_frame. frame0 -> start_frame, frame1 ->
    end_frame. start_frame is either a plain reference image or, per Luma's
    "extend" mechanic, {"generation_id": <a COMPLETED prior generation's id>}
    to forward-continue from that clip's ending — this is how multiple outfit
    images become one continuous multi-shot video instead of a single call
    with N images (ray-3.2 also supports up to 64 keyframes in one call via
    video.keyframes/keyframe_indexes, but that caps total duration at 10s,
    which doesn't fit "each outfit gets its own several-second shot" — hence
    chaining single-keyframe-pair calls instead, same as the ray-2 design)."""
    return {
        "model": "ray-3.2",
        "type": "video",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "video": {
            "resolution": resolution,
            "duration": f"{duration_seconds}s",
            "start_frame": _keyframe(frame0),
            "end_frame": _keyframe(frame1),
        },
    }
