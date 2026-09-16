import httpx

from app.luma import LumaClient, build_generation_payload


def test_generation_payload_contains_all_reference_images_and_video_settings():
    payload = build_generation_payload(
        prompt="showcase the outfit",
        outfit_urls=["https://example.test/outfit-1", "https://example.test/outfit-2"],
        background_url="https://example.test/background",
        aspect_ratio="9:16",
        duration_seconds=8,
    )

    assert payload["type"] == "video"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["duration"] == 8
    assert payload["prompt"] == "showcase the outfit"
    assert payload["reference_images"] == [
        "https://example.test/outfit-1",
        "https://example.test/outfit-2",
        "https://example.test/background",
    ]


def test_luma_client_returns_provider_generation_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(201, json={"id": "provider-job-1", "status": "queued"})

    client = LumaClient(
        api_key="test-key",
        endpoint="https://luma.test/v1/generations",
        transport=httpx.MockTransport(handler),
    )

    result = client.create_generation({"prompt": "test"})

    assert result == {"provider_id": "provider-job-1", "status": "queued"}
