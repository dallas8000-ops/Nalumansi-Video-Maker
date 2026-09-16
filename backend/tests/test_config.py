from app.config import Settings


def test_settings_reads_luma_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("LUMA_API_KEY", "test-luma-key")

    settings = Settings()

    assert settings.luma_api_key == "test-luma-key"
