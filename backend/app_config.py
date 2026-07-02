import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

PRODUCTION = "production"
LOCAL_FRONTEND_ORIGIN = "http://localhost:3000"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class AppConfigurationError(RuntimeError):
    """Raised when application deployment settings are invalid."""


def parse_boolean(name: str, value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise AppConfigurationError(
        f"{name} must be one of: {', '.join(sorted(TRUE_VALUES | FALSE_VALUES))}"
    )


def validate_origin(origin: str, *, production: bool) -> str:
    normalized = origin.strip().rstrip("/")
    parsed = urlsplit(normalized)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise AppConfigurationError(
            "CORS_ALLOWED_ORIGINS entries must be HTTP(S) origins without paths"
        )

    if production:
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or hostname in {"localhost", "127.0.0.1", "::1"}
            or "*" in hostname
        ):
            raise AppConfigurationError(
                "Production CORS origins must use HTTPS and cannot be localhost"
            )

    return normalized


@dataclass(frozen=True)
class AppSettings:
    environment: str
    cors_allowed_origins: tuple[str, ...]
    docs_enabled: bool

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "AppSettings":
        values = environment if environment is not None else os.environ
        app_environment = values.get("APP_ENV", "development").strip().lower()
        production = app_environment == PRODUCTION

        raw_origins = values.get("CORS_ALLOWED_ORIGINS", "")
        if not raw_origins.strip():
            if production:
                raise AppConfigurationError(
                    "CORS_ALLOWED_ORIGINS is required when APP_ENV=production"
                )
            raw_origins = LOCAL_FRONTEND_ORIGIN

        origins = tuple(
            dict.fromkeys(
                validate_origin(origin, production=production)
                for origin in raw_origins.split(",")
                if origin.strip()
            )
        )
        if not origins:
            raise AppConfigurationError(
                "CORS_ALLOWED_ORIGINS must contain at least one origin"
            )

        requested_docs = parse_boolean(
            "ENABLE_API_DOCS",
            values.get("ENABLE_API_DOCS"),
            default=True,
        )

        return cls(
            environment=app_environment,
            cors_allowed_origins=origins,
            docs_enabled=requested_docs and not production,
        )
