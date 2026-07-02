import json
from collections.abc import Iterator
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import cards_api
from auth import AuthenticatedUser, get_current_user
from card_models import CardCreate, CardResponse, CardUpdate
from cards_repository import CardNotFoundError
from image_storage import (
    ImageStorageDeletionError,
    ImageStoragePersistenceError,
    StoredCardImage,
)
from image_validation import ValidatedImage
from main import app

USER_ID = UUID("d686b83b-80fd-480a-b60b-f4f69b3ef311")
CARD_ID = UUID("8e926c43-a64d-485c-80e8-e22fe63d78ba")
ACCESS_TOKEN = "test-access-token"
IMAGE_ID = UUID("9a50528e-6390-44da-a5e0-88e42115ab55")
CARD_PAYLOAD = {
    "card_name": "Monkey D. Luffy",
    "set": "Romance Dawn",
    "card_number": "OP01-024",
    "rarity": "Rare",
    "condition_guess": "Near Mint",
    "suggested_price": "$10.00",
    "ebay_title": "Monkey D. Luffy OP01-024",
    "ebay_description": "One Piece trading card.",
}


class FakeCardsRepository:
    def __init__(self, cards: list[CardResponse]) -> None:
        self.cards = cards
        self.list_owner_id: UUID | None = None
        self.list_access_token: str | None = None
        self.list_q: str | None = None
        self.list_status: str | None = None
        self.list_set_name: str | None = None
        self.list_rarity: str | None = None
        self.list_limit: int | None = None
        self.create_owner_id: UUID | None = None
        self.create_access_token: str | None = None
        self.created_card: CardCreate | None = None
        self.deleted_card_id: UUID | None = None
        self.update_owner_id: UUID | None = None
        self.update_access_token: str | None = None
        self.updated_card_id: UUID | None = None
        self.updated_card: CardUpdate | None = None
        self.raise_on_update: Exception | None = None
        self.raise_on_delete: Exception | None = None

    def list_cards(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        q: str | None = None,
        status: str | None = None,
        set_name: str | None = None,
        rarity: str | None = None,
        limit: int = 50,
    ) -> list[CardResponse]:
        self.list_owner_id = owner_id
        self.list_access_token = access_token
        self.list_q = q
        self.list_status = status
        self.list_set_name = set_name
        self.list_rarity = rarity
        self.list_limit = limit
        return self.cards

    def create_card(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card: CardCreate,
    ) -> CardResponse:
        self.create_owner_id = owner_id
        self.create_access_token = access_token
        self.created_card = card
        return self.cards[0]

    def delete_card(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> None:
        if self.raise_on_delete is not None:
            raise self.raise_on_delete

        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        self.deleted_card_id = card_id

    def update_card(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
        card_update: CardUpdate,
    ) -> CardResponse:
        if self.raise_on_update is not None:
            raise self.raise_on_update

        self.update_owner_id = owner_id
        self.update_access_token = access_token
        self.updated_card_id = card_id
        self.updated_card = card_update

        return self.cards[0].model_copy(
            update={
                "card_name": card_update.card_name or self.cards[0].card_name,
                "set": card_update.set or self.cards[0].set,
                "card_number": card_update.card_number or self.cards[0].card_number,
                "rarity": card_update.rarity or self.cards[0].rarity,
                "condition_guess": card_update.condition_guess
                or self.cards[0].condition_guess,
                "price_amount": card_update.price_amount
                if "price_amount" in card_update.model_fields_set
                else self.cards[0].price_amount,
                "currency": card_update.currency or self.cards[0].currency,
                "status": card_update.status or self.cards[0].status,
                "suggested_price": "$12.50"
                if card_update.price_amount is not None
                else self.cards[0].suggested_price,
            }
        )


class FakeImageStorage:
    def __init__(self) -> None:
        self.persisted = False
        self.fail_persistence = False
        self.persist_owner_id: UUID | None = None
        self.deleted_card_id: UUID | None = None
        self.raise_on_delete: Exception | None = None

    def attach_signed_urls(
        self,
        *,
        cards: list[CardResponse],
        owner_id: UUID,
        access_token: str,
    ) -> dict[UUID, tuple[UUID, str]]:
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        return {cards[0].id: (IMAGE_ID, "http://example.test/signed-image")}

    def persist_card_image(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
        image: ValidatedImage,
    ) -> StoredCardImage:
        if self.fail_persistence:
            raise ImageStoragePersistenceError(
                "test persistence failure",
                cleanup_complete=True,
            )
        assert card_id == CARD_ID
        assert access_token == ACCESS_TOKEN
        assert image.content_type == "image/png"
        self.persist_owner_id = owner_id
        self.persisted = True
        return StoredCardImage(
            image_id=IMAGE_ID,
            card_id=CARD_ID,
            storage_path=f"{USER_ID}/{CARD_ID}/{IMAGE_ID}.png",
        )

    def create_signed_url(self, **kwargs: object) -> str:
        return "http://example.test/signed-image"

    def delete_card_images(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
    ) -> None:
        if self.raise_on_delete is not None:
            raise self.raise_on_delete

        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        self.deleted_card_id = card_id


def png_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def card_response() -> CardResponse:
    return CardResponse.model_validate(
        {
            **CARD_PAYLOAD,
            "id": CARD_ID,
            "created_at": datetime(2026, 7, 1, tzinfo=UTC),
        }
    )


@pytest.fixture
def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        claims={"sub": str(USER_ID), "role": "authenticated"},
        access_token=ACCESS_TOKEN,
    )


@pytest.fixture
def authenticated_client(authenticated_user: AuthenticatedUser) -> Iterator[TestClient]:
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_cards_reject_unauthenticated_requests(method: str) -> None:
    with TestClient(app) as client:
        if method == "POST":
            response = client.post("/cards", data={"card": json.dumps(CARD_PAYLOAD)})
        elif method == "PATCH":
            response = client.patch(f"/cards/{CARD_ID}", json={"card_name": "Updated"})
        elif method == "DELETE":
            response = client.delete(f"/cards/{CARD_ID}")
        else:
            response = client.get("/cards")

    assert response.status_code == 401


def test_list_cards_uses_authenticated_user(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.get("/cards")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(CARD_ID)
    assert response.json()[0]["image_id"] == str(IMAGE_ID)
    assert response.json()[0]["image_url"] == "http://example.test/signed-image"
    assert repository.list_owner_id == USER_ID
    assert repository.list_access_token == ACCESS_TOKEN
    assert repository.list_status is None
    assert repository.list_limit == 50


def test_list_cards_forwards_search_and_filters(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.get(
        "/cards",
        params={
            "q": "Luffy",
            "status": "active",
            "set_name": "Romance",
            "rarity": "Rare",
            "limit": 25,
        },
    )

    assert response.status_code == 200
    assert repository.list_owner_id == USER_ID
    assert repository.list_q == "Luffy"
    assert repository.list_status == "active"
    assert repository.list_set_name == "Romance"
    assert repository.list_rarity == "Rare"
    assert repository.list_limit == 25


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"limit": 0}, 422),
        ({"limit": 101}, 422),
        ({"status": "unknown"}, 422),
    ],
)
def test_list_cards_rejects_invalid_filters(
    authenticated_client: TestClient,
    params: dict[str, object],
    expected_status: int,
) -> None:
    response = authenticated_client.get("/cards", params=params)

    assert response.status_code == expected_status


def test_create_card_attaches_authenticated_owner(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)

    response = authenticated_client.post(
        "/cards",
        data={"card": json.dumps(CARD_PAYLOAD)},
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(CARD_ID)
    assert repository.create_owner_id == USER_ID
    assert repository.create_access_token == ACCESS_TOKEN
    assert repository.created_card == CardCreate.model_validate(CARD_PAYLOAD)


def test_create_card_persists_owner_image(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.post(
        "/cards",
        data={"card": json.dumps(CARD_PAYLOAD)},
        files={"image": ("card.png", png_image(), "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["image_id"] == str(IMAGE_ID)
    assert response.json()["image_url"] == "http://example.test/signed-image"
    assert image_storage.persisted is True
    assert image_storage.persist_owner_id == USER_ID


def test_create_card_deletes_card_after_clean_image_failure(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    image_storage.fail_persistence = True
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.post(
        "/cards",
        data={"card": json.dumps(CARD_PAYLOAD)},
        files={"image": ("card.png", png_image(), "image/png")},
    )

    assert response.status_code == 502
    assert repository.deleted_card_id == CARD_ID


def test_update_card_uses_authenticated_owner(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.patch(
        f"/cards/{CARD_ID}",
        json={
            "card_name": "Updated Luffy",
            "set": "Paramount War",
            "card_number": "OP02-001",
            "rarity": "Super Rare",
            "condition_guess": "Lightly Played",
            "price_amount": "12.50",
            "currency": "usd",
            "status": "active",
        },
    )

    assert response.status_code == 200
    assert response.json()["card_name"] == "Updated Luffy"
    assert response.json()["price_amount"] == "12.50"
    assert response.json()["currency"] == "USD"
    assert response.json()["status"] == "active"
    assert response.json()["image_url"] == "http://example.test/signed-image"
    assert repository.update_owner_id == USER_ID
    assert repository.update_access_token == ACCESS_TOKEN
    assert repository.updated_card_id == CARD_ID


def test_update_card_rejects_cross_user_access(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    repository.raise_on_update = CardNotFoundError("Card not found")
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.patch(
        f"/cards/{CARD_ID}",
        json={"card_name": "Attempted cross-user update"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"


def test_archive_card_updates_status_for_owner(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.patch(f"/cards/{CARD_ID}/archive")

    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert repository.updated_card is not None
    assert repository.updated_card.status == "archived"


def test_archive_card_is_idempotent(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archived_card = card_response.model_copy(update={"status": "archived"})
    repository = FakeCardsRepository([archived_card])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    first_response = authenticated_client.patch(f"/cards/{CARD_ID}/archive")
    second_response = authenticated_client.patch(f"/cards/{CARD_ID}/archive")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["status"] == "archived"
    assert second_response.json()["status"] == "archived"


def test_archive_card_rejects_cross_user_access(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    repository.raise_on_update = CardNotFoundError("Card not found")
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.patch(f"/cards/{CARD_ID}/archive")

    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"


def test_delete_card_cleans_up_images_and_deletes_owner_card(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.delete(f"/cards/{CARD_ID}")

    assert response.status_code == 204
    assert image_storage.deleted_card_id == CARD_ID
    assert repository.deleted_card_id == CARD_ID


def test_delete_card_rejects_cross_user_access(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    repository.raise_on_delete = CardNotFoundError("Card not found")
    image_storage = FakeImageStorage()
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.delete(f"/cards/{CARD_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"


def test_delete_card_returns_error_when_image_cleanup_fails(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    image_storage = FakeImageStorage()
    image_storage.raise_on_delete = ImageStorageDeletionError("cleanup failed")
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)
    monkeypatch.setattr(cards_api, "get_image_storage", lambda: image_storage)

    response = authenticated_client.delete(f"/cards/{CARD_ID}")

    assert response.status_code == 502
    assert repository.deleted_card_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"id": str(CARD_ID)},
        {"owner_id": str(USER_ID)},
        {"created_at": "2026-07-01T00:00:00Z"},
        {"image_id": str(IMAGE_ID)},
        {"storage_path": f"{USER_ID}/{CARD_ID}/{IMAGE_ID}.png"},
        {"status": "invalid"},
        {"currency": "US"},
        {"price_amount": "-1.00"},
    ],
)
def test_update_card_rejects_invalid_or_immutable_fields(
    authenticated_client: TestClient,
    payload: dict[str, str],
) -> None:
    response = authenticated_client.patch(f"/cards/{CARD_ID}", json=payload)

    assert response.status_code == 422
