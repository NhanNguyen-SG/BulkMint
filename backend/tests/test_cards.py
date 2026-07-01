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
from card_models import CardCreate, CardResponse
from image_storage import ImageStoragePersistenceError, StoredCardImage
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
        self.create_owner_id: UUID | None = None
        self.create_access_token: str | None = None
        self.created_card: CardCreate | None = None
        self.deleted_card_id: UUID | None = None

    def list_cards(self, *, owner_id: UUID, access_token: str) -> list[CardResponse]:
        self.list_owner_id = owner_id
        self.list_access_token = access_token
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
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        self.deleted_card_id = card_id


class FakeImageStorage:
    def __init__(self) -> None:
        self.persisted = False
        self.fail_persistence = False
        self.persist_owner_id: UUID | None = None

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


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_cards_reject_unauthenticated_requests(method: str) -> None:
    with TestClient(app) as client:
        if method == "POST":
            response = client.post("/cards", data={"card": json.dumps(CARD_PAYLOAD)})
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
