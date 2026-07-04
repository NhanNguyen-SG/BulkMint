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
from image_validation import ImageObject, ValidatedImage

OWNER_ID = UUID("bc9d03b8-5765-4832-ac48-837f7e461e76")
CARD_ID = UUID("1e474701-bff7-4bda-919f-8db21f34c93c")
IMAGE_ID = UUID("72c1f7a7-a33b-49f9-b79f-32a1b5f6364d")
ACCESS_TOKEN = "test-access-token"


@pytest.fixture
def image() -> ValidatedImage:
    return ValidatedImage(
        original=ImageObject(
            content=b"original-png",
            content_type="image/png",
            extension="png",
            byte_size=12,
            sha256="a" * 64,
        ),
        normalized=ImageObject(
            content=b"normalized-jpeg",
            content_type="image/jpeg",
            extension="jpg",
            byte_size=15,
            sha256="b" * 64,
        ),
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
    metadata_payloads: list[dict[str, object]] = []
    uploaded_objects: list[tuple[str, bytes, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))

        if request.method == "POST" and request.url.path == "/rest/v1/card_images":
            metadata_payloads.append(json.loads(request.content))
            return httpx.Response(201)
        if request.method == "POST" and request.url.path.startswith(
            "/storage/v1/object/card-images/"
        ):
            uploaded_objects.append(
                (
                    request.url.path,
                    request.content,
                    request.headers["content-type"],
                )
            )
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

    assert stored.storage_path == f"{OWNER_ID}/{CARD_ID}/{stored.image_id}.jpg"
    assert stored.original_image_id is not None
    assert stored.original_storage_path == f"{OWNER_ID}/{CARD_ID}/{stored.original_image_id}.png"
    assert metadata_payloads == [
        {
            "id": str(stored.original_image_id),
            "owner_id": str(OWNER_ID),
            "card_id": str(CARD_ID),
            "storage_bucket": "card-images",
            "storage_path": stored.original_storage_path,
            "image_kind": "other",
            "mime_type": "image/png",
            "byte_size": 12,
            "sha256": "a" * 64,
            "status": "pending",
        },
        {
            "id": str(stored.image_id),
            "owner_id": str(OWNER_ID),
            "card_id": str(CARD_ID),
            "storage_bucket": "card-images",
            "storage_path": stored.storage_path,
            "image_kind": "front",
            "mime_type": "image/jpeg",
            "byte_size": 15,
            "sha256": "b" * 64,
            "status": "pending",
        },
    ]
    assert [(content, content_type) for _path, content, content_type in uploaded_objects] == [
        (image.original.content, "image/png"),
        (image.normalized.content, "image/jpeg"),
    ]
    assert [method for method, _path in requests] == [
        "POST",
        "POST",
        "POST",
        "POST",
        "PATCH",
        "PATCH",
    ]


def test_attach_signed_url_returns_private_image(
    card: CardResponse,
) -> None:
    storage_path = f"{OWNER_ID}/{CARD_ID}/{IMAGE_ID}.png"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/rest/v1/card_images":
            assert request.url.params["image_kind"] == "eq.front"
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
    assert images[CARD_ID][1].startswith("https://test-project.supabase.co/storage/v1/object/sign/")


def test_get_card_image_for_generation_downloads_owned_active_front_image() -> None:
    storage_path = f"{OWNER_ID}/{CARD_ID}/{IMAGE_ID}.jpg"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/v1/card_images":
            assert request.url.params["owner_id"] == f"eq.{OWNER_ID}"
            assert request.url.params["card_id"] == f"eq.{CARD_ID}"
            assert request.url.params["status"] == "eq.active"
            assert request.url.params["image_kind"] == "eq.front"
            return httpx.Response(
                200,
                json=[
                    {
                        "storage_bucket": "card-images",
                        "storage_path": storage_path,
                        "mime_type": "image/jpeg",
                    }
                ],
            )
        if request.url.path.startswith("/storage/v1/object/authenticated/card-images/"):
            assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
            return httpx.Response(200, content=b"stored-card-image")
        return httpx.Response(500, json={"message": "unexpected request"})

    storage = SupabaseImageStorage(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )
    image = storage.get_card_image_for_generation(
        owner_id=OWNER_ID,
        card_id=CARD_ID,
        access_token=ACCESS_TOKEN,
    )

    assert image is not None
    assert image.content == b"stored-card-image"
    assert image.content_type == "image/jpeg"


def test_get_card_image_for_generation_returns_none_without_metadata() -> None:
    storage = SupabaseImageStorage(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[])),
    )

    assert (
        storage.get_card_image_for_generation(
            owner_id=OWNER_ID,
            card_id=CARD_ID,
            access_token=ACCESS_TOKEN,
        )
        is None
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
        "POST",
        "DELETE",
        "DELETE",
        "DELETE",
    ]


def test_normalized_upload_failure_removes_original_and_both_metadata_rows(
    image: ValidatedImage,
) -> None:
    requests: list[tuple[str, str]] = []
    upload_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal upload_count
        requests.append((request.method, request.url.path))

        if request.method == "POST" and request.url.path == "/rest/v1/card_images":
            return httpx.Response(201)
        if request.method == "POST" and request.url.path.startswith(
            "/storage/v1/object/card-images/"
        ):
            upload_count += 1
            if upload_count == 1:
                return httpx.Response(200)
            return httpx.Response(500, json={"message": "normalized upload failed"})
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
        "POST",
        "POST",
        "DELETE",
        "DELETE",
        "DELETE",
        "DELETE",
    ]


def test_delete_card_images_removes_objects_and_metadata() -> None:
    storage_path = f"{OWNER_ID}/{CARD_ID}/{IMAGE_ID}.png"
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))

        if request.method == "GET" and request.url.path == "/rest/v1/card_images":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(IMAGE_ID),
                        "card_id": str(CARD_ID),
                        "storage_path": storage_path,
                    }
                ],
            )
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

    storage.delete_card_images(
        owner_id=OWNER_ID,
        card_id=CARD_ID,
        access_token=ACCESS_TOKEN,
    )

    assert [method for method, _path in requests] == ["GET", "DELETE", "DELETE"]
