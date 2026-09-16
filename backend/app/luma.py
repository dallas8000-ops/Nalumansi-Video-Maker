from typing import Any

import httpx


class LumaClient:
    def __init__(self, api_key: str, endpoint: str, transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None):
        self.api_key = api_key
        self.endpoint = endpoint
        self.transport = transport

    def create_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(transport=self.transport, timeout=30) as client:
            response = client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        provider_id = body.get("id") or body.get("generation_id")
        if not provider_id:
            raise ValueError("Luma response did not include a generation id")
        return {"provider_id": provider_id, "status": body.get("status", "queued")}


def build_generation_payload(
    *,
    prompt: str,
    outfit_urls: list[str],
    background_url: str,
    aspect_ratio: str,
    duration_seconds: int,
) -> dict[str, Any]:
    return {
        "type": "video",
        "model": "uni-1",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": duration_seconds,
        "reference_images": [*outfit_urls, background_url],
    }