import json
from collections.abc import Iterator
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
from auth import AuthenticatedUser, get_current_user
from image_validation import MAX_IMAGE_BYTES
from main import app

USER_ID = UUID("9fe0413d-9038-4da6-8f5f-dccaa95b7922")
ANALYSIS_RESULT = {
    "card_name": "Test Card",
    "set": "Test Set",
    "card_number": "TEST-001",
    "rarity": "Rare",
    "condition_guess": "Near Mint",
    "suggested_price": "$5.00",
    "ebay_title": "Test Card",
    "ebay_description": "Test description",
}


@pytest.fixture
def authenticated_client() -> Iterator[TestClient]:
    user = AuthenticatedUser(
        user_id=USER_ID,
        claims={"sub": str(USER_ID), "role": "authenticated"},
        access_token="test-access-token",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def png_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_is_public_and_minimal() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_card_rejects_missing_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/analyze-card",
            files={"file": ("card.png", png_image(), "image/png")},
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_status"),
    [
        ("card.txt", b"not an image", "text/plain", 415),
        ("card.jpg", b"x" * (MAX_IMAGE_BYTES + 1), "image/jpeg", 413),
        ("card.png", b"not an image", "image/png", 400),
    ],
)
def test_analyze_card_validates_upload(
    authenticated_client: TestClient,
    filename: str,
    content: bytes,
    content_type: str,
    expected_status: int,
) -> None:
    response = authenticated_client.post(
        "/analyze-card",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == expected_status


def test_analyze_card_accepts_readable_image(
    authenticated_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(ANALYSIS_RESULT))
            )
        ]
    )
    create_completion = Mock(return_value=completion)
    openai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_completion),
        )
    )
    monkeypatch.setattr(main, "get_openai_client", lambda: openai_client)

    response = authenticated_client.post(
        "/analyze-card",
        files={"file": ("card.png", png_image(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == ANALYSIS_RESULT
    request = create_completion.call_args.kwargs
    image_url = request["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
