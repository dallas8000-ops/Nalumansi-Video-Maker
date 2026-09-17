from typing import Any, Literal

import httpx

# A keyframe is either a fresh image ("image", url) or a continuation of a
# previously *completed* generation ("generation", generation_id) — Luma's
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
    """Build a ray-3.2 Agents API video request.

    Image-to-video pins only the outfit as the first frame. Pairing an empty
    showroom as start and the outfit photo as end makes Luma morph one picture
    into the other, which changes the background and produces ugly motion.

    5s uses start_frame. 10s cannot use start_frame, so it uses a single
    keyframe at index 0.

    Forward-extend from a completed clip can only send a single
    `start_frame.generation_id`, and not with 10s, so extend steps are 5s.
    """
    if frame0[0] == "generation":
        video: dict[str, Any] = {
            "resolution": resolution,
            "duration": "5s",
            "start_frame": {"generation_id": frame0[1]},
        }
    elif duration_seconds == 10:
        video = {
            "resolution": resolution,
            "duration": "10s",
            "keyframes": [_keyframe(frame1)],
            "keyframe_indexes": [0],
        }
    else:
        video = {
            "resolution": resolution,
            "duration": f"{duration_seconds}s",
            "start_frame": _keyframe(frame1),
        }
    return {
        "model": "ray-3.2",
        "type": "video",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "video": video,
    }
