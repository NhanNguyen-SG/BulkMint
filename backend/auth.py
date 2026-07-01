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

ALLOWED_ALGORITHMS = ("ES256", "RS256")
AUTHENTICATED_ROLE = "authenticated"


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
        jwks_url = (
            os.getenv("SUPABASE_JWKS_URL")
            or f"{supabase_url}/auth/v1/.well-known/jwks.json"
        )

        return cls(issuer=issuer, audience=audience, jwks_url=jwks_url)

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["aud", "exp", "iss", "role", "sub"]},
            )
        except (InvalidTokenError, PyJWKClientError, ValueError) as error:
            raise JWTVerificationError("Invalid access token") from error

        if claims.get("role") != AUTHENTICATED_ROLE:
            raise JWTVerificationError("Invalid access token role")

        try:
            user_id = UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError) as error:
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
