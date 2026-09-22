import httpx

from app.luma import LumaClient, build_generation_payload


def test_generation_payload_uses_ray_3_2_and_pins_the_outfit_photo_as_start_frame():
    payload = build_generation_payload(
        prompt="showcase the outfit",
        image_url="https://example.test/outfit-1",
        aspect_ratio="9:16",
        duration_seconds=5,
    )

    assert payload["model"] == "ray-3.2"
    assert payload["type"] == "video"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["prompt"] == "showcase the outfit"
    assert payload["video"] == {
        "resolution": "1080p",
        "duration": "5s",
        "start_frame": {"url": "https://example.test/outfit-1"},
    }


def test_generation_payload_at_10s_uses_a_single_keyframe_not_start_frame():
    # ray-3.2 rejects start_frame/end_frame at duration=10s; only multi-keyframe
    # mode is valid there. This is what previously produced Luma's 400s at 10s
    # (fixed for real by switching format, not just shortening duration).
    payload = build_generation_payload(
        prompt="showcase the outfit",
        image_url="https://example.test/outfit-1",
        aspect_ratio="9:16",
        duration_seconds=10,
    )

    assert payload["video"] == {
        "resolution": "1080p",
        "duration": "10s",
        "keyframes": [{"url": "https://example.test/outfit-1"}],
        "keyframe_indexes": [0],
    }


def test_generation_payload_never_chains_via_generation_id():
    # Regression guard for the actual bug: build_generation_payload must never
    # accept or emit a generation_id anchor, because ray-3.2's Agents API
    # can't combine that with a new reference image in one call — any chaining
    # attempt silently drops the new outfit's photo. Every call must be a
    # fresh image-to-video request from that outfit's own photo.
    import inspect

    signature = inspect.signature(build_generation_payload)
    assert "frame0" not in signature.parameters
    assert "frame1" not in signature.parameters
    payload = build_generation_payload(
        prompt="p", image_url="https://example.test/x", aspect_ratio="9:16", duration_seconds=5
    )
    assert "generation_id" not in str(payload)


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


def test_luma_client_raises_with_response_body_on_http_error():
    # _raise_for_luma_status exists specifically so a 400/401/403 carries
    # Luma's actual error detail into the job's failure_reason instead of a
    # generic httpx status error — this is what earlier let a wrong-model 403
    # get diagnosed at all.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text='{"detail":"video.duration: invalid"}')

    client = LumaClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.create_generation({"model": "ray-3.2", "type": "video", "prompt": "test"})
        assert False, "expected ValueError"
    except ValueError as error:
        assert "400" in str(error)
        assert "invalid" in str(error)
