import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClientError
from jwt.exceptions import PyJWKClientConnectionError

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


def test_verification_failure_logs_only_sanitized_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    other_private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    sensitive_email = "private@example.com"
    token = jwt.encode(
        {
            "aud": AUDIENCE,
            "email": sensitive_email,
            "exp": now + timedelta(minutes=5),
            "iss": ISSUER,
            "role": "authenticated",
            "sub": str(USER_ID),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "production-key"},
    )
    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.return_value = SimpleNamespace(
        key=other_private_key.public_key(),
        key_id="production-key",
    )
    verifier = make_verifier(jwks_client)

    with caplog.at_level(logging.WARNING, logger="auth"):
        with pytest.raises(auth.JWTVerificationError):
            verifier.verify(token)

    message = caplog.messages[-1]
    assert "exception_class=InvalidSignatureError" in message
    assert "exception_message=Signature verification failed" in message
    assert "alg=ES256" in message
    assert "kid=production-key" in message
    assert f"iss={ISSUER}" in message
    assert f"aud={AUDIENCE}" in message
    assert "jwks_lookup_succeeded=True" in message
    assert "matching_key_id_found=True" in message
    assert token not in message
    assert str(USER_ID) not in message
    assert sensitive_email not in message


def test_jwks_connection_failure_logs_lookup_outcome(
    caplog: pytest.LogCaptureFixture,
    private_key: rsa.RSAPrivateKey,
) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": AUDIENCE,
            "exp": now + timedelta(minutes=5),
            "iss": ISSUER,
            "role": "authenticated",
            "sub": str(USER_ID),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unavailable-key"},
    )
    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientConnectionError(
        "JWKS endpoint unavailable"
    )
    verifier = make_verifier(jwks_client)

    with caplog.at_level(logging.WARNING, logger="auth"):
        with pytest.raises(auth.JWTVerificationError):
            verifier.verify(token)

    message = caplog.messages[-1]
    assert "exception_class=PyJWKClientConnectionError" in message
    assert "jwks_lookup_succeeded=False" in message
    assert "matching_key_id_found=False" in message


def test_missing_matching_key_logs_successful_jwks_lookup(
    caplog: pytest.LogCaptureFixture,
    private_key: rsa.RSAPrivateKey,
) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": AUDIENCE,
            "exp": now + timedelta(minutes=5),
            "iss": ISSUER,
            "role": "authenticated",
            "sub": str(USER_ID),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "missing-key"},
    )
    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.side_effect = PyJWKClientError(
        'Unable to find a signing key that matches: "missing-key"'
    )
    verifier = make_verifier(jwks_client)

    with caplog.at_level(logging.WARNING, logger="auth"):
        with pytest.raises(auth.JWTVerificationError):
            verifier.verify(token)

    message = caplog.messages[-1]
    assert "exception_class=PyJWKClientError" in message
    assert "jwks_lookup_succeeded=True" in message
    assert "matching_key_id_found=False" in message


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
