import httpx

from app.luma import LumaClient, build_generation_payload


def test_generation_payload_uses_keyframes_and_string_duration():
    payload = build_generation_payload(
        prompt="showcase the outfit",
        frame0=("image", "https://example.test/background"),
        frame1=("image", "https://example.test/outfit-1"),
        aspect_ratio="9:16",
        duration_seconds=9,
    )

    assert payload["model"] == "ray-2"
    assert payload["generation_type"] == "video"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["duration"] == "9s"
    assert payload["prompt"] == "showcase the outfit"
    assert payload["keyframes"] == {
        "frame0": {"type": "image", "url": "https://example.test/background"},
        "frame1": {"type": "image", "url": "https://example.test/outfit-1"},
    }


def test_generation_payload_supports_chaining_from_a_prior_generation():
    payload = build_generation_payload(
        prompt="continue the showcase",
        frame0=("generation", "gen-1"),
        frame1=("image", "https://example.test/outfit-2"),
        aspect_ratio="9:16",
        duration_seconds=5,
    )

    assert payload["keyframes"]["frame0"] == {"type": "generation", "id": "gen-1"}


def test_luma_client_posts_to_dream_machine_video_endpoint_and_reads_state():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.lumalabs.ai/dream-machine/v1/generations/video"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(201, json={"id": "provider-job-1", "state": "dreaming"})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.create_generation({"model": "ray-2", "prompt": "test"})

    # Luma's response field is "state", not "status" — this pins that down so a
    # future edit can't silently regress back to always reporting "queued".
    assert result["provider_id"] == "provider-job-1"
    assert result["status"] == "dreaming"


def test_luma_client_get_generation_reads_assets_and_failure_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.lumalabs.ai/dream-machine/v1/generations/provider-job-1"
        return httpx.Response(
            200,
            json={
                "id": "provider-job-1",
                "state": "failed",
                "failure_reason": "content policy violation",
                "assets": {"video": None},
            },
        )

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.get_generation("provider-job-1")

    assert result == {
        "provider_id": "provider-job-1",
        "status": "failed",
        "video_url": None,
        "failure_reason": "content policy violation",
    }


def test_luma_client_raises_when_response_has_no_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"state": "queued"})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.create_generation({"model": "ray-2", "prompt": "test"})
        assert False, "expected ValueError"
    except ValueError:
        pass
