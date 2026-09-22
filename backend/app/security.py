import hmac

from fastapi import Header, HTTPException, status

from app.config import Settings

_settings = Settings()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Gate cost-incurring endpoints (queueing a Luma generation, uploading
    an asset) behind a shared-secret header.

    Currently every write endpoint on this API is open to the public
    internet with no auth at all: anyone who has (or guesses/leaks) the
    Railway URL can call POST /api/generations and spend your Luma credits,
    or POST /api/assets to fill your disk. That is the actual finding —
    this dependency is the fix.

    It is opt-in and OFF by default (no enforcement) unless APP_API_KEY is
    set in the environment, specifically so deploying this file does not
    immediately break the live Android app before it's updated to send the
    header. To activate: set APP_API_KEY on Railway (and locally in .env),
    then have the Android client send that same value as `X-API-Key` on
    every POST to /api/generations and /api/assets.
    """
    if not _settings.app_api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, _settings.app_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing or invalid API key")
