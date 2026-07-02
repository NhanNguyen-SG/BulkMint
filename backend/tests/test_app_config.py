import pytest

from app_config import (
    LOCAL_FRONTEND_ORIGIN,
    AppConfigurationError,
    AppSettings,
)


def test_development_defaults_preserve_local_frontend_and_docs() -> None:
    settings = AppSettings.from_environment({})

    assert settings.environment == "development"
    assert settings.cors_allowed_origins == (LOCAL_FRONTEND_ORIGIN,)
    assert settings.docs_enabled is True


def test_production_requires_explicit_cors_origins() -> None:
    with pytest.raises(
        AppConfigurationError,
        match="CORS_ALLOWED_ORIGINS is required",
    ):
        AppSettings.from_environment({"APP_ENV": "production"})


def test_production_accepts_https_origins_and_always_disables_docs() -> None:
    settings = AppSettings.from_environment(
        {
            "APP_ENV": "production",
            "CORS_ALLOWED_ORIGINS": (
                "https://bulkmint.example, https://www.bulkmint.example/"
            ),
            "ENABLE_API_DOCS": "true",
        }
    )

    assert settings.cors_allowed_origins == (
        "https://bulkmint.example",
        "https://www.bulkmint.example",
    )
    assert settings.docs_enabled is False


@pytest.mark.parametrize(
    "origin",
    [
        "http://bulkmint.example",
        "https://bulkmint.example/path",
        "https://user:password@bulkmint.example",
        "http://localhost:3000",
        "https://*.vercel.app",
    ],
)
def test_production_rejects_unsafe_origins(origin: str) -> None:
    with pytest.raises(AppConfigurationError):
        AppSettings.from_environment(
            {
                "APP_ENV": "production",
                "CORS_ALLOWED_ORIGINS": origin,
            }
        )


def test_invalid_docs_flag_is_rejected() -> None:
    with pytest.raises(AppConfigurationError, match="ENABLE_API_DOCS"):
        AppSettings.from_environment({"ENABLE_API_DOCS": "sometimes"})
