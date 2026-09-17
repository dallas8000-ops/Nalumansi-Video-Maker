import httpx

from app.luma import LumaClient, build_generation_payload


def test_generation_payload_nests_video_fields_and_uses_ray_3_2():
    payload = build_generation_payload(
        prompt="showcase the outfit",
        frame0=("image", "https://example.test/background"),
        frame1=("image", "https://example.test/outfit-1"),
        aspect_ratio="9:16",
        duration_seconds=10,
    )

    assert payload["model"] == "ray-3.2"
    assert payload["type"] == "video"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["prompt"] == "showcase the outfit"
    assert payload["video"] == {
        "resolution": "720p",
        "duration": "10s",
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
    assert payload["video"]["duration"] == "5s"


def test_luma_client_posts_to_agents_generations_endpoint_and_reads_state():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://agents.lumalabs.ai/v1/generations"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(201, json={"id": "provider-job-1", "state": "queued", "output": []})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.create_generation({"model": "ray-3.2", "type": "video", "prompt": "test"})

    # ray-3.2's response field is "state", not "status" — this pins that down so a
    # future edit can't silently regress back to always reporting "queued".
    assert result["provider_id"] == "provider-job-1"
    assert result["status"] == "queued"
    assert result["video_url"] is None


def test_luma_client_get_generation_reads_output_url_and_failure_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://agents.lumalabs.ai/v1/generations/provider-job-1"
        return httpx.Response(
            200,
            json={
                "id": "provider-job-1",
                "state": "failed",
                "failure_reason": "content policy violation",
                "output": [],
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


def test_luma_client_get_generation_reads_completed_video_url_from_output_list():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "provider-job-1",
                "state": "completed",
                "failure_reason": None,
                "output": [{"type": "video", "url": "https://cdn.test/presigned-clip.mp4"}],
            },
        )

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.get_generation("provider-job-1")

    assert result["status"] == "completed"
    assert result["video_url"] == "https://cdn.test/presigned-clip.mp4"


def test_luma_client_raises_when_response_has_no_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"state": "queued", "output": []})

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.create_generation({"model": "ray-3.2", "type": "video", "prompt": "test"})
        assert False, "expected ValueError"
    except ValueError:
        pass
