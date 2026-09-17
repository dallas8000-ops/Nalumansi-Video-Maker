import httpx

from app.luma import LumaClient, build_generation_payload


def test_generation_payload_uses_agents_video_schema():
    payload = build_generation_payload(
        prompt="showcase the outfit",
        frame0=("image", "https://example.test/background"),
        frame1=("image", "https://example.test/outfit-1"),
        aspect_ratio="9:16",
        duration_seconds=9,
    )

    assert payload["model"] == "ray-3.2"
    assert payload["prompt"] == "showcase the outfit"
    assert payload["video"] == {
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "duration": "9s",
        "start_frame": {"url": "https://example.test/background"},
        "end_frame": {"url": "https://example.test/outfit-1"},
    }


def test_generation_payload_supports_chaining_from_a_prior_generation():
    payload = build_generation_payload(
        prompt="continue the showcase",
        frame0=("generation", "gen-1"),
        frame1=("image", "https://example.test/outfit-2"),
        aspect_ratio="9:16",
        duration_seconds=5,
    )

    assert payload["video"]["start_frame"] == {"generation_id": "gen-1"}


def test_luma_client_posts_to_agents_video_endpoint_and_reads_state():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://agents.lumalabs.ai/v1/generations"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.json()["model"] == "ray-3.2"
        return httpx.Response(201, json={"id": "provider-job-1", "state": "dreaming", "output": []})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.create_generation({"model": "ray-2", "prompt": "test"})

    # Luma's response field is "state", not "status" — this pins that down so a
    # future edit can't silently regress back to always reporting "queued".
    assert result["provider_id"] == "provider-job-1"
    assert result["status"] == "dreaming"


def test_luma_client_get_generation_reads_output_video_and_failure_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://agents.lumalabs.ai/v1/generations/provider-job-1"
        return httpx.Response(
            200,
            json={
                "id": "provider-job-1",
                "state": "completed",
                "failure_reason": None,
                "output": [{"url": "https://example.test/video.mp4"}],
            },
        )

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.get_generation("provider-job-1")

    assert result == {
        "provider_id": "provider-job-1",
        "status": "completed",
        "video_url": "https://example.test/video.mp4",
        "failure_reason": None,
    }


def test_luma_client_raises_when_response_has_no_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"state": "queued", "output": []})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.create_generation({"model": "ray-2", "prompt": "test"})
        assert False, "expected ValueError"
    except ValueError:
        pass
