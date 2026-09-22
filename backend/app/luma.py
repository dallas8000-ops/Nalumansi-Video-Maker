from typing import Any

import httpx

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
        _raise_for_luma_status(response)
        body = response.json()
        if not body.get("id"):
            raise ValueError("Luma response did not include a generation id")
        return _serialize(body)

    def get_generation(self, generation_id: str) -> dict[str, Any]:
        response = self._client.get(f"{BASE_URL}/generations/{generation_id}", headers=self._headers)
        _raise_for_luma_status(response)
        return _serialize(response.json())


def _raise_for_luma_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    detail = response.text.strip() or response.reason_phrase
    raise ValueError(f"Luma {response.status_code}: {detail}")


def _serialize(body: dict[str, Any]) -> dict[str, Any]:
    output = body.get("output") or []
    return {
        "provider_id": body.get("id"),
        "status": body.get("state") or "queued",
        "video_url": output[0]["url"] if output else None,
        "failure_reason": body.get("failure_reason"),
    }


def build_generation_payload(
    *,
    prompt: str,
    image_url: str,
    aspect_ratio: str,
    duration_seconds: int,
    resolution: str = "1080p",
) -> dict[str, Any]:
    """Build a ray-3.2 Agents API image-to-video request for one outfit.

    Every outfit is an INDEPENDENT generation from that outfit's own photo —
    never a continuation of the previous outfit's clip. This is not a
    stylistic choice, it's forced by the API: ray-3.2's Agents API "extension
    flows accept only a single generation_id anchor ... not alongside
    additional image references" (docs.agents.lumalabs.ai/guides/videos/
    generation). You cannot pass a prior generation_id as start_frame AND a
    new image as end_frame/keyframe in the same call.

    The previous version of this function got this wrong: for outfit 2+ it
    built a payload with ONLY `start_frame: {generation_id: <previous>}` and
    silently dropped the new outfit's photo, because the caller passed it as
    `frame1` and this function never read `frame1` on the extend branch. The
    practical effect was that outfits after the first never appeared in the
    generated video at all — the "chain" was just Luma extending outfit #1's
    clip with no new visual reference, N times.
    """
    if duration_seconds == 10:
        # end_frame/start_frame pairs cap out at 5s; only multi-keyframe mode
        # is valid at 10s, so a single still becomes a one-keyframe request.
        video: dict[str, Any] = {
            "resolution": resolution,
            "duration": "10s",
            "keyframes": [{"url": image_url}],
            "keyframe_indexes": [0],
        }
    else:
        video = {
            "resolution": resolution,
            "duration": f"{duration_seconds}s",
            "start_frame": {"url": image_url},
        }
    return {
        "model": "ray-3.2",
        "type": "video",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "video": video,
    }
