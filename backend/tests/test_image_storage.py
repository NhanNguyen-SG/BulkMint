import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from card_models import CardResponse
from image_storage import (
    ImageStoragePersistenceError,
    SupabaseImageStorage,
)
from image_validation import ValidatedImage

OWNER_ID = UUID("bc9d03b8-5765-4832-ac48-837f7e461e76")
CARD_ID = UUID("1e474701-bff7-4bda-919f-8db21f34c93c")
IMAGE_ID = UUID("72c1f7a7-a33b-49f9-b79f-32a1b5f6364d")
ACCESS_TOKEN = "test-access-token"


@pytest.fixture
def image() -> ValidatedImage:
    return ValidatedImage(
        content=b"validated-image",
        content_type="image/png",
        extension="png",
        byte_size=15,
        sha256="a" * 64,
    )


@pytest.fixture
def card() -> CardResponse:
    return CardResponse(
        id=CARD_ID,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        card_name="Test Card",
        set="Test Set",
        card_number="TEST-001",
        rarity="Rare",
        condition_guess="Near Mint",
        suggested_price="$5.00",
        ebay_title="Test Card",
        ebay_description="Test description",
    )


def test_persist_card_image_uses_server_generated_owner_path(
    image: ValidatedImage,
) -> None:
    requests: list[tuple[str, str]] = []
    metadata_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))

        if request.method == "POST" and request.url.path == "/rest/v1/card_images":
            metadata_payload.update(json.loads(request.content))
            return httpx.Response(201)
        if request.method == "POST" and request.url.path.startswith(
            "/storage/v1/object/card-images/"
        ):
            assert request.content == image.content
            assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
            return httpx.Response(200, json={"Key": "card-images/test"})
        if request.method == "PATCH" and request.url.path == "/rest/v1/card_images":
            assert json.loads(request.content) == {"status": "active"}
            return httpx.Response(204)

        return httpx.Response(500, json={"message": "unexpected request"})

    storage = SupabaseImageStorage(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    stored = storage.persist_card_image(
        owner_id=OWNER_ID,
        card_id=CARD_ID,
        access_token=ACCESS_TOKEN,
        image=image,
    )

    assert stored.storage_path == f"{OWNER_ID}/{CARD_ID}/{stored.image_id}.png"
    assert metadata_payload["owner_id"] == str(OWNER_ID)
    assert metadata_payload["card_id"] == str(CARD_ID)
    assert metadata_payload["id"] == str(stored.image_id)
    assert metadata_payload["storage_path"] == stored.storage_path
    assert metadata_payload["status"] == "pending"
    assert [method for method, _path in requests] == ["POST", "POST", "PATCH"]


def test_attach_signed_url_returns_private_image(
    card: CardResponse,
) -> None:
    storage_path = f"{OWNER_ID}/{CARD_ID}/{IMAGE_ID}.png"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/rest/v1/card_images":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(IMAGE_ID),
                        "card_id": str(CARD_ID),
                        "storage_bucket": "card-images",
                        "storage_path": storage_path,
                    }
                ],
            )
        if request.method == "POST" and request.url.path.startswith(
            "/storage/v1/object/sign/card-images/"
        ):
            assert json.loads(request.content) == {"expiresIn": 300}
            return httpx.Response(
                200,
                json={"signedURL": "/object/sign/card-images/test?token=test"},
            )

        return httpx.Response(500, json={"message": "unexpected request"})

    storage = SupabaseImageStorage(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    images = storage.attach_signed_urls(
        cards=[card],
        owner_id=OWNER_ID,
        access_token=ACCESS_TOKEN,
    )

    assert images[CARD_ID][0] == IMAGE_ID
    assert images[CARD_ID][1].startswith(
        "https://test-project.supabase.co/storage/v1/object/sign/"
    )


def test_upload_failure_cleans_object_and_metadata(
    image: ValidatedImage,
) -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))

        if request.method == "POST" and request.url.path == "/rest/v1/card_images":
            return httpx.Response(201)
        if request.method == "POST" and request.url.path.startswith(
            "/storage/v1/object/card-images/"
        ):
            return httpx.Response(500, json={"message": "upload failed"})
        if request.method == "DELETE" and request.url.path.startswith(
            "/storage/v1/object/card-images/"
        ):
            return httpx.Response(200)
        if request.method == "DELETE" and request.url.path == "/rest/v1/card_images":
            return httpx.Response(204)

        return httpx.Response(500, json={"message": "unexpected request"})

    storage = SupabaseImageStorage(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ImageStoragePersistenceError) as raised:
        storage.persist_card_image(
            owner_id=OWNER_ID,
            card_id=CARD_ID,
            access_token=ACCESS_TOKEN,
            image=image,
        )

    assert raised.value.cleanup_complete is True
    assert [method for method, _path in requests] == [
        "POST",
        "POST",
        "DELETE",
        "DELETE",
    ]
