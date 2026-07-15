from collections.abc import Iterator
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from auth import AuthenticatedUser, get_current_user
from card_detector import (
    CardDetectionSettings,
    DetectionCandidate,
    OpenCVCardDetector,
)
from image_validation import MAX_IMAGE_BYTES, ImageObject, ValidatedImage
from main import app

USER_ID = UUID("51a9c68c-8a0b-4a1f-8ee6-50fd6231dc92")


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


def image_bytes(
    *,
    cards: list[tuple[int, int, int, int]],
    size: tuple[int, int] = (1200, 900),
    image_format: str = "PNG",
) -> bytes:
    image = Image.new("RGB", size, color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    for x, y, width, height in cards:
        draw.rectangle(
            (x, y, x + width, y + height),
            fill=(232, 232, 232),
            outline=(20, 20, 20),
            width=8,
        )
        if width > 60 and height > 60:
            draw.rectangle(
                (x + 24, y + 24, x + width - 24, y + height - 24),
                outline=(90, 90, 90),
                width=3,
            )

    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def detect_from_bytes(content: bytes) -> int:
    image_object = ImageObject(
        content=content,
        content_type="image/png",
        extension="png",
        byte_size=len(content),
        sha256="0" * 64,
    )
    upload = ValidatedImage(
        original=image_object,
        normalized=image_object,
    )
    return OpenCVCardDetector().detect(upload).count


def test_detect_cards_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/detect-cards",
            files={"file": ("cards.png", image_bytes(cards=[]), "image/png")},
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_status"),
    [
        ("cards.txt", b"not an image", "text/plain", 415),
        ("cards.jpg", b"x" * (MAX_IMAGE_BYTES + 1), "image/jpeg", 413),
        ("cards.png", b"not an image", "image/png", 400),
    ],
)
def test_detect_cards_validates_upload(
    authenticated_client: TestClient,
    filename: str,
    content: bytes,
    content_type: str,
    expected_status: int,
) -> None:
    response = authenticated_client.post(
        "/detect-cards",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == expected_status


def test_detect_cards_endpoint_returns_boxes_and_debug_image(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/detect-cards",
        files={
            "file": (
                "cards.png",
                image_bytes(cards=[(120, 120, 260, 370), (520, 120, 260, 370)]),
                "image/png",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["image_width"] > 0
    assert body["image_height"] > 0
    assert body["count"] == 2
    assert len(body["detections"]) == 2
    assert body["detections"][0]["index"] == 0
    assert body["detections"][0]["confidence"] > 0
    assert body["debug_image"].startswith("data:image/jpeg;base64,")


def test_detector_finds_one_clear_rectangular_card() -> None:
    assert detect_from_bytes(image_bytes(cards=[(200, 150, 300, 420)])) == 1


def test_detector_finds_multiple_non_overlapping_cards() -> None:
    assert (
        detect_from_bytes(
            image_bytes(cards=[(80, 90, 240, 340), (420, 90, 240, 340), (760, 90, 240, 340)])
        )
        == 3
    )


def test_detector_returns_no_cards_for_blank_image() -> None:
    assert detect_from_bytes(image_bytes(cards=[])) == 0


def test_detector_rejects_tiny_contours() -> None:
    assert detect_from_bytes(image_bytes(cards=[(40, 40, 30, 44)])) == 0


def test_detector_suppresses_duplicate_overlapping_boxes() -> None:
    candidates = [
        DetectionCandidate(x=10, y=10, width=300, height=420, confidence=0.9, area=126000),
        DetectionCandidate(x=20, y=20, width=300, height=420, confidence=0.8, area=125000),
        DetectionCandidate(x=500, y=10, width=300, height=420, confidence=0.7, area=126000),
    ]

    selected = OpenCVCardDetector._suppress_and_sort(candidates)

    assert [(item.x, item.y) for item in selected] == [(10, 10), (500, 10)]


def test_detector_respects_maximum_detection_limit() -> None:
    settings = CardDetectionSettings()
    candidates = [
        DetectionCandidate(
            x=index * 20,
            y=index * 20,
            width=10,
            height=14,
            confidence=0.9,
            area=140,
        )
        for index in range(settings.max_detection_count + 5)
    ]

    selected = OpenCVCardDetector._suppress_and_sort(candidates, settings)

    assert len(selected) == settings.max_detection_count


@pytest.mark.parametrize(
    "cards",
    [
        [(180, 120, 260, 370)],
        [(160, 200, 420, 280)],
    ],
)
def test_detector_accepts_portrait_and_landscape_cards(
    cards: list[tuple[int, int, int, int]],
) -> None:
    assert detect_from_bytes(image_bytes(cards=cards)) == 1
