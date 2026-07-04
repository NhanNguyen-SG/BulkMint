import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError
from jwt.exceptions import PyJWKClientConnectionError

ALLOWED_ALGORITHMS = ("ES256", "RS256")
AUTHENTICATED_ROLE = "authenticated"
LOG_VALUE_LIMIT = 256

logger = logging.getLogger(__name__)


class JWTVerificationError(Exception):
    """Raised when a bearer token cannot be verified as a Supabase user."""


class AuthConfigurationError(RuntimeError):
    """Raised when required backend authentication settings are absent."""


class SigningKey(Protocol):
    key: Any


class JWKSClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> SigningKey: ...


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    claims: Mapping[str, Any]
    access_token: str = field(repr=False)


@dataclass(frozen=True)
class JWTDiagnosticMetadata:
    alg: str | None = None
    kid: str | None = None
    iss: str | None = None
    aud: str | list[str] | None = None
    sensitive_values: tuple[str, ...] = field(default=(), repr=False)


def _diagnostic_metadata(token: str) -> JWTDiagnosticMetadata:
    header: Mapping[str, Any] = {}
    claims: Mapping[str, Any] = {}

    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError:
        pass

    try:
        unverified_claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        if isinstance(unverified_claims, Mapping):
            claims = unverified_claims
    except InvalidTokenError:
        pass

    sensitive_values = tuple(
        value
        for key in ("sub", "email", "phone")
        if isinstance(value := claims.get(key), str) and value
    )
    audience = claims.get("aud")

    return JWTDiagnosticMetadata(
        alg=header.get("alg") if isinstance(header.get("alg"), str) else None,
        kid=header.get("kid") if isinstance(header.get("kid"), str) else None,
        iss=claims.get("iss") if isinstance(claims.get("iss"), str) else None,
        aud=audience
        if isinstance(audience, str)
        or (isinstance(audience, list) and all(isinstance(value, str) for value in audience))
        else None,
        sensitive_values=sensitive_values,
    )


def _sanitize_log_value(value: object, *, redactions: tuple[str, ...] = ()) -> str:
    sanitized = str(value).replace("\r", "\\r").replace("\n", "\\n")
    for sensitive_value in redactions:
        sanitized = sanitized.replace(sensitive_value, "[REDACTED]")
    if len(sanitized) > LOG_VALUE_LIMIT:
        return f"{sanitized[:LOG_VALUE_LIMIT]}…"
    return sanitized


def _log_verification_failure(
    error: Exception,
    *,
    token: str,
    metadata: JWTDiagnosticMetadata,
    jwks_lookup_succeeded: bool,
    matching_key_id_found: bool,
) -> None:
    logger.warning(
        "JWT verification failed "
        "exception_class=%s exception_message=%s alg=%s kid=%s iss=%s aud=%s "
        "jwks_lookup_succeeded=%s matching_key_id_found=%s",
        type(error).__name__,
        _sanitize_log_value(
            error,
            redactions=(token, *metadata.sensitive_values),
        ),
        _sanitize_log_value(metadata.alg),
        _sanitize_log_value(metadata.kid),
        _sanitize_log_value(metadata.iss),
        _sanitize_log_value(metadata.aud),
        jwks_lookup_succeeded,
        matching_key_id_found,
    )


class SupabaseJWTVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        jwks_client: JWKSClient | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self._jwks_client = jwks_client or PyJWKClient(
            jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=600,
            timeout=5,
        )

    @classmethod
    def from_environment(cls) -> "SupabaseJWTVerifier":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        if not supabase_url:
            raise AuthConfigurationError("SUPABASE_URL is required")

        issuer = os.getenv("SUPABASE_JWT_ISSUER") or f"{supabase_url}/auth/v1"
        audience = os.getenv("SUPABASE_JWT_AUDIENCE", AUTHENTICATED_ROLE)
        jwks_url = os.getenv("SUPABASE_JWKS_URL") or f"{supabase_url}/auth/v1/.well-known/jwks.json"

        return cls(issuer=issuer, audience=audience, jwks_url=jwks_url)

    def verify(self, token: str) -> AuthenticatedUser:
        metadata = _diagnostic_metadata(token)
        jwks_lookup_succeeded = False
        matching_key_id_found = False

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            jwks_lookup_succeeded = True
            signing_key_id = getattr(signing_key, "key_id", metadata.kid)
            matching_key_id_found = signing_key_id == metadata.kid
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["aud", "exp", "iss", "role", "sub"]},
            )
        except (InvalidTokenError, PyJWKClientError, ValueError) as error:
            if isinstance(error, PyJWKClientError) and not isinstance(
                error, PyJWKClientConnectionError
            ):
                jwks_lookup_succeeded = True
            _log_verification_failure(
                error,
                token=token,
                metadata=metadata,
                jwks_lookup_succeeded=jwks_lookup_succeeded,
                matching_key_id_found=matching_key_id_found,
            )
            raise JWTVerificationError("Invalid access token") from error

        if claims.get("role") != AUTHENTICATED_ROLE:
            role_error = JWTVerificationError("Invalid access token role")
            _log_verification_failure(
                role_error,
                token=token,
                metadata=metadata,
                jwks_lookup_succeeded=jwks_lookup_succeeded,
                matching_key_id_found=matching_key_id_found,
            )
            raise role_error

        try:
            user_id = UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError) as error:
            _log_verification_failure(
                error,
                token=token,
                metadata=metadata,
                jwks_lookup_succeeded=jwks_lookup_succeeded,
                matching_key_id_found=matching_key_id_found,
            )
            raise JWTVerificationError("Invalid access token subject") from error

        return AuthenticatedUser(
            user_id=user_id,
            claims=claims,
            access_token=token,
        )


@lru_cache
def get_verifier() -> SupabaseJWTVerifier:
    return SupabaseJWTVerifier.from_environment()


bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()

    try:
        verifier = get_verifier()
        return verifier.verify(credentials.credentials)
    except AuthConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from error
    except JWTVerificationError as error:
        raise unauthorized() from error
