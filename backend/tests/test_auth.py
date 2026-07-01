from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClientError

import auth
from auth import SupabaseJWTVerifier
from main import app

ISSUER = "https://test-project.supabase.co/auth/v1"
AUDIENCE = "authenticated"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
USER_ID = UUID("8f951565-d73f-4ba7-a1c6-63d6b47b6308")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_verifier(jwks_client: Mock) -> SupabaseJWTVerifier:
    return SupabaseJWTVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        jwks_client=jwks_client,
    )


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_rejects_invalid_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("invalid token")
    monkeypatch.setattr(auth, "get_verifier", lambda: make_verifier(jwks_client))

    response = client.get("/me", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_accepts_valid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    private_key: rsa.RSAPrivateKey,
) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": AUDIENCE,
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "iss": ISSUER,
            "role": "authenticated",
            "sub": str(USER_ID),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.return_value = SimpleNamespace(
        key=private_key.public_key()
    )
    monkeypatch.setattr(auth, "get_verifier", lambda: make_verifier(jwks_client))

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user_id": str(USER_ID)}
    jwks_client.get_signing_key_from_jwt.assert_called_once_with(token)
