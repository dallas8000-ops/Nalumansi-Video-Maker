import re
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import imageio_ffmpeg
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings
from app.luma import LumaClient, TERMINAL_STATES, build_generation_payload
from app.models import AudioSettings, GenerationRequest

app = FastAPI(title="Nalumansi Video Maker API")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
ALLOWED_KINDS = {"outfit", "background", "music"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
GENERATION_JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 20 * 60  # generous ceiling per Luma segment; a hung poll fails the job instead of hanging it forever
settings = Settings()


def _update_job(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        GENERATION_JOBS[job_id].update(fields)


def _resolve_asset_path(asset_id: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
        return None
    matches = list(UPLOAD_DIR.glob(f"{asset_id}.*"))
    return matches[0] if matches else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/generations", status_code=status.HTTP_202_ACCEPTED)
def queue_generation(request: GenerationRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    job_id = uuid4().hex
    outfit_ids = request.outfit_asset_ids or ([request.outfit_asset_id] if request.outfit_asset_id else [])
    if not outfit_ids:
        raise HTTPException(status_code=422, detail="at least one outfit asset is required")

    base = settings.public_base_url.rstrip("/")
    outfit_urls = [f"{base}/api/assets/{asset_id}" for asset_id in outfit_ids]
    background_url = f"{base}/api/assets/{request.background_asset_id}"

    music_path: Path | None = None
    if request.audio.music_asset_id:
        music_path = _resolve_asset_path(request.audio.music_asset_id)
        if music_path is None:
            raise HTTPException(status_code=422, detail="music asset not found")

    GENERATION_JOBS[job_id] = {
        "status": "running",
        "step": 0,
        "total_steps": len(outfit_urls),
        "provider_ids": [],
        "video_url": None,
        "error": None,
    }
    background_tasks.add_task(
        run_generation_chain,
        job_id=job_id,
        outfit_urls=outfit_urls,
        background_url=background_url,
        music_path=music_path,
        audio=request.audio,
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        duration_seconds=request.duration_seconds,
    )
    return {"job_id": job_id, **GENERATION_JOBS[job_id]}


@app.get("/api/generations/{job_id}")
def get_generation_status(job_id: str) -> dict[str, object]:
    job = GENERATION_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="generation job not found")
    return {"job_id": job_id, **job}


def run_generation_chain(
    *,
    job_id: str,
    outfit_urls: list[str],
    background_url: str,
    music_path: Path | None,
    audio: AudioSettings,
    prompt: str,
    aspect_ratio: str,
    duration_seconds: int,
    client: LumaClient | None = None,
) -> None:
    """N outfit photos become N chained Luma calls. The first shot is
    image-to-video from the outfit photo only (not background → outfit), so
    Luma does not morph an empty room into a person. Later shots extend from
    the previous completed generation. Segments are downloaded and concatenated,
    with uploaded music muxed in — Luma clips have no audio of their own."""
    client = client or LumaClient(settings.luma_api_key)
    frame0 = ("image", background_url)
    segment_paths: list[Path] = []

    try:
        for index, outfit_url in enumerate(outfit_urls, start=1):
            _update_job(job_id, step=index)
            payload = build_generation_payload(
                prompt=prompt,
                frame0=frame0,
                frame1=("image", outfit_url),
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            )
            created = client.create_generation(payload)
            with JOBS_LOCK:
                GENERATION_JOBS[job_id]["provider_ids"].append(created["provider_id"])

            generation = _await_completion(client, created["provider_id"])
            if generation["status"] != "completed":
                _update_job(
                    job_id,
                    status="failed",
                    error=generation.get("failure_reason") or f"segment {index} of {len(outfit_urls)} failed",
                )
                return
            if not generation.get("video_url"):
                _update_job(
                    job_id,
                    status="failed",
                    error=f"segment {index} of {len(outfit_urls)} completed with no video asset",
                )
                return

            segment_paths.append(_download_video(OUTPUT_DIR / f"{job_id}-segment-{index}.mp4", generation["video_url"]))
            frame0 = ("generation", created["provider_id"])

        final_path = _assemble_final_video(job_id, segment_paths, music_path, audio)
        _update_job(
            job_id,
            status="completed",
            video_url=f"{settings.public_base_url.rstrip('/')}/api/videos/{final_path.name}",
        )
    except Exception as error:  # this background task has no caller to propagate to — the job record IS the error channel
        _update_job(job_id, status="failed", error=str(error))
    finally:
        for path in segment_paths:
            path.unlink(missing_ok=True)


def _await_completion(client: LumaClient, provider_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    generation = client.get_generation(provider_id)
    while generation["status"] not in TERMINAL_STATES:
        if time.monotonic() > deadline:
            return {**generation, "status": "failed", "failure_reason": "timed out waiting for Luma to finish this segment"}
        time.sleep(POLL_INTERVAL_SECONDS)
        generation = client.get_generation(provider_id)
    return generation


def _download_video(destination: Path, video_url: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", video_url, timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
    return destination


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(args, capture_output=True, text=True, check=True)


def _has_audio_stream(ffmpeg_exe: str, path: Path) -> bool:
    # imageio-ffmpeg bundles ffmpeg but not ffprobe; ffmpeg itself prints
    # stream info to stderr even with no output, which is enough to detect
    # an audio stream without a second binary.
    result = subprocess.run([ffmpeg_exe, "-i", str(path)], capture_output=True, text=True)
    return "Audio:" in result.stderr


def _concatenate_segments(ffmpeg_exe: str, segment_paths: list[Path], destination: Path) -> None:
    if len(segment_paths) == 1:
        destination.write_bytes(segment_paths[0].read_bytes())
        return

    list_file = destination.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in segment_paths), encoding="utf-8")
    try:
        try:
            _run_ffmpeg([ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(destination)])
        except subprocess.CalledProcessError:
            # Stream-copy concat requires byte-identical codec parameters across
            # segments; that can vary slightly between separate Luma calls, so
            # fall back to a re-encode, which tolerates that mismatch.
            _run_ffmpeg([ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), str(destination)])
    finally:
        list_file.unlink(missing_ok=True)


def _mux_audio(ffmpeg_exe: str, video_path: Path, music_path: Path | None, audio: AudioSettings, destination: Path) -> None:
    has_original_audio = _has_audio_stream(ffmpeg_exe, video_path)

    if music_path is None:
        if audio.mute_original_audio and has_original_audio:
            _run_ffmpeg([ffmpeg_exe, "-y", "-i", str(video_path), "-c:v", "copy", "-an", str(destination)])
        else:
            video_path.replace(destination)
        return

    delay_ms = max(0, int(audio.music_start_seconds * 1000))
    if audio.mute_original_audio or not has_original_audio:
        filter_complex = f"[1:a]adelay={delay_ms}|{delay_ms},volume={audio.music_volume}[aout]"
    else:
        filter_complex = (
            f"[0:a]volume={audio.original_audio_volume}[a0];"
            f"[1:a]adelay={delay_ms}|{delay_ms},volume={audio.music_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    _run_ffmpeg(
        [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-i", str(music_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(destination),
        ]
    )


def _assemble_final_video(job_id: str, segment_paths: list[Path], music_path: Path | None, audio: AudioSettings) -> Path:
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    concatenated = OUTPUT_DIR / f"{job_id}-concat.mp4"
    final_path = OUTPUT_DIR / f"{job_id}.mp4"

    _concatenate_segments(ffmpeg_exe, segment_paths, concatenated)
    try:
        _mux_audio(ffmpeg_exe, concatenated, music_path, audio, final_path)
    finally:
        concatenated.unlink(missing_ok=True)
    return final_path


@app.post("/api/assets", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    kind: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, str]:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail="kind must be outfit or background")
    expected_type = "audio/" if kind == "music" else "image/"
    if not file.content_type or not file.content_type.startswith(expected_type):
        raise HTTPException(status_code=415, detail=f"only {expected_type[:-1]} uploads are supported")

    extension = Path(file.filename or "").suffix.lower()
    allowed_extensions = ALLOWED_AUDIO_EXTENSIONS if kind == "music" else ALLOWED_IMAGE_EXTENSIONS
    if extension not in allowed_extensions:
        raise HTTPException(status_code=415, detail=f"unsupported {kind} extension")

    asset_id = uuid4().hex
    destination = UPLOAD_DIR / f"{asset_id}{extension}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(await file.read())

    return {
        "asset_id": asset_id,
        "kind": kind,
        "filename": destination.name,
        "url": f"{settings.public_base_url.rstrip('/')}/api/assets/{asset_id}",
    }


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str) -> FileResponse:
    path = _resolve_asset_path(asset_id)
    if path is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(path)


@app.get("/api/videos/{video_name}")
def get_video(video_name: str) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{32}\.mp4", video_name):
        raise HTTPException(status_code=404, detail="video not found")
    path = OUTPUT_DIR / video_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(path, media_type="video/mp4")
