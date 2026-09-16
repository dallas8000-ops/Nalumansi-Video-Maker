# Nalumansi Video Maker

Android and FastAPI foundation for creating social videos from outfit and background images.

## Secret setup

Open `backend/.env` and replace the placeholder value with a newly generated Luma API key. Keep that file local; it is ignored by Git. The key must stay on the backend and must never be placed in the Android app.

## Backend

```powershell
Set-Location backend
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload
```

The health check is available at `http://127.0.0.1:8000/health`.

## Android

Open the project root in Android Studio. The Android SDK path is read from the local machine, and the project uses Kotlin, Jetpack Compose, and Material 3.
