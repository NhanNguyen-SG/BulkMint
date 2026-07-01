from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import cards_api
from auth import AuthenticatedUser, get_current_user
from card_models import CardCreate, CardResponse
from main import app

USER_ID = UUID("d686b83b-80fd-480a-b60b-f4f69b3ef311")
CARD_ID = UUID("8e926c43-a64d-485c-80e8-e22fe63d78ba")
ACCESS_TOKEN = "test-access-token"
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


@pytest.fixture
def card_response() -> CardResponse:
    return CardResponse(
        id=CARD_ID,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        **CARD_PAYLOAD,
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
            response = client.post("/cards", json=CARD_PAYLOAD)
        else:
            response = client.get("/cards")

    assert response.status_code == 401


def test_list_cards_uses_authenticated_user(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)

    response = authenticated_client.get("/cards")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(CARD_ID)
    assert repository.list_owner_id == USER_ID
    assert repository.list_access_token == ACCESS_TOKEN


def test_create_card_attaches_authenticated_owner(
    authenticated_client: TestClient,
    card_response: CardResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeCardsRepository([card_response])
    monkeypatch.setattr(cards_api, "get_cards_repository", lambda: repository)

    response = authenticated_client.post("/cards", json=CARD_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["id"] == str(CARD_ID)
    assert repository.create_owner_id == USER_ID
    assert repository.create_access_token == ACCESS_TOKEN
    assert repository.created_card == CardCreate.model_validate(CARD_PAYLOAD)
