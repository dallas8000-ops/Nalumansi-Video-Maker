from pathlib import Path
import re
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.models import GenerationRequest
from app.config import Settings


app = FastAPI(title="Nalumansi Video Maker API")
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"
ALLOWED_KINDS = {"outfit", "background"}
ALLOWED_KINDS.add("music")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
GENERATION_JOBS: dict[str, dict[str, str]] = {}
settings = Settings()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/generations", status_code=status.HTTP_202_ACCEPTED)
def queue_generation(request: GenerationRequest) -> dict[str, str]:
    job_id = uuid4().hex
    GENERATION_JOBS[job_id] = {"status": "queued"}
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/generations/{job_id}")
def get_generation_status(job_id: str) -> dict[str, str]:
    job = GENERATION_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="generation job not found")
    return {"job_id": job_id, **job}


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
    if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
        raise HTTPException(status_code=404, detail="asset not found")

    matches = list(UPLOAD_DIR.glob(f"{asset_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="asset not found")

    return FileResponse(matches[0])
