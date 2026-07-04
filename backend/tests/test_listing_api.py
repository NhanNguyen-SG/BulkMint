from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import listing_api
from auth import AuthenticatedUser, get_current_user
from image_storage import CardImageForGeneration
from listing_generation import LISTING_PROMPT_VERSION
from listing_models import (
    ListingDraftCreate,
    ListingDraftResponse,
    ListingDraftUpdate,
)
from listing_repository import (
    ListingCardContext,
    ListingCardNotFoundError,
    ListingDraftNotFoundError,
)
from main import app

USER_ID = UUID("7b3fc397-08da-4fc2-b6fd-ed760f6f51be")
CARD_ID = UUID("68ff5cf5-34be-430a-bc23-319642fd120b")
DRAFT_ID = UUID("e790cb39-e31a-4c40-b911-afc96b66fb14")
OBSERVATION_ID = UUID("89b98619-123f-4cb9-90e5-a0dd7fda1145")
ACCESS_TOKEN = "listing-test-token"


class FakeListingRepository:
    def __init__(self, draft: ListingDraftResponse) -> None:
        self.draft = draft
        self.raise_on_card: Exception | None = None
        self.raise_on_get: Exception | None = None
        self.card_checked: UUID | None = None
        self.created_input: ListingDraftCreate | None = None
        self.created_observation_id: UUID | None = None
        self.updated_input: ListingDraftUpdate | None = None
        self.updated_observation_id: UUID | None = None

    def assert_card_owned(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> None:
        if self.raise_on_card is not None:
            raise self.raise_on_card
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        self.card_checked = card_id

    def get_card_context(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> ListingCardContext:
        self.assert_card_owned(
            owner_id=owner_id,
            access_token=access_token,
            card_id=card_id,
        )
        return ListingCardContext(
            card_id=card_id,
            card_name="Monkey D. Luffy",
            set_name="Romance Dawn",
            card_number="OP01-024",
            rarity="Rare",
            condition_guess="Near Mint",
            price_amount=Decimal("12.34"),
            currency="USD",
        )

    def create_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
        draft: ListingDraftCreate,
        selected_pricing_observation_id: UUID | None,
    ) -> ListingDraftResponse:
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        assert card_id == CARD_ID
        self.created_input = draft
        self.created_observation_id = selected_pricing_observation_id
        return self.draft.model_copy(
            update={
                "title": draft.title,
                "description": draft.description,
                "item_specifics_json": draft.item_specifics_json,
                "category_suggestion": draft.category_suggestion,
                "price_amount": draft.price_amount,
                "currency": draft.currency,
                "selected_pricing_observation_id": selected_pricing_observation_id,
                "content_origin": "ai_generated",
                "prompt_version": draft.prompt_version,
                "ai_model": draft.generation_model,
            }
        )

    def list_drafts(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> list[ListingDraftResponse]:
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        assert card_id == CARD_ID
        return [self.draft]

    def get_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        draft_id: UUID,
    ) -> ListingDraftResponse:
        if self.raise_on_get is not None:
            raise self.raise_on_get
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        assert draft_id == DRAFT_ID
        return self.draft

    def update_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        draft_id: UUID,
        draft_update: ListingDraftUpdate,
        selected_pricing_observation_id: UUID | None = None,
    ) -> ListingDraftResponse:
        assert owner_id == USER_ID
        assert access_token == ACCESS_TOKEN
        assert draft_id == DRAFT_ID
        self.updated_input = draft_update
        self.updated_observation_id = selected_pricing_observation_id
        return self.draft.model_copy(
            update={
                "version": self.draft.version + 1,
                "status": draft_update.status or self.draft.status,
                "title": draft_update.title or self.draft.title,
                "description": draft_update.description or self.draft.description,
                "item_specifics_json": (
                    draft_update.item_specifics_json
                    if draft_update.item_specifics_json is not None
                    else self.draft.item_specifics_json
                ),
                "category_suggestion": (
                    draft_update.category_suggestion
                    if "category_suggestion" in draft_update.model_fields_set
                    else self.draft.category_suggestion
                ),
                "price_amount": (
                    draft_update.price_amount
                    if draft_update.changes_price
                    else self.draft.price_amount
                ),
                "currency": draft_update.currency or self.draft.currency,
                "selected_pricing_observation_id": (
                    selected_pricing_observation_id
                    if selected_pricing_observation_id is not None
                    else self.draft.selected_pricing_observation_id
                ),
            }
        )


class FakePricingRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_ai_estimate(self, **kwargs: object) -> UUID:
        self.calls.append(kwargs)
        return OBSERVATION_ID

    def create_manual_observation(self, **kwargs: object) -> UUID:
        self.calls.append(kwargs)
        return OBSERVATION_ID


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def create_listing_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


class FakeImageStorage:
    def __init__(self) -> None:
        self.image = CardImageForGeneration(
            content=b"test-card-image",
            content_type="image/png",
        )
        self.calls: list[dict[str, object]] = []

    def get_card_image_for_generation(self, **kwargs: object) -> CardImageForGeneration:
        self.calls.append(kwargs)
        return self.image


class FakeGenerationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> ListingDraftCreate:
        self.calls.append(kwargs)
        return ListingDraftCreate.model_validate(
            {
                "title": "Monkey D. Luffy OP01-024 Rare",
                "description": "AI-generated review draft for the saved card.",
                "condition_summary": "Appears Near Mint; review the image.",
                "item_specifics_json": {
                    "condition_summary": "Appears Near Mint; review the image.",
                    "item_specifics": {
                        "Game": "One Piece Card Game",
                        "Set": "Romance Dawn",
                    },
                    "keywords": ["Luffy", "OP01-024", "Romance Dawn"],
                },
                "category_suggestion": "Collectible Card Games",
                "price_amount": "12.34",
                "currency": "USD",
                "generation_model": "gpt-4.1-mini",
                "prompt_version": LISTING_PROMPT_VERSION,
                "generated_at": datetime(2026, 7, 2, tzinfo=UTC),
            }
        )


@pytest.fixture
def draft_response() -> ListingDraftResponse:
    return ListingDraftResponse.model_validate(
        {
            "id": DRAFT_ID,
            "card_id": CARD_ID,
            "marketplace_target": "ebay",
            "version": 1,
            "status": "draft",
            "title": "Monkey D. Luffy OP01-024 Rare",
            "description": "AI-generated review draft for the saved card.",
            "item_specifics_json": {
                "condition_summary": "Appears Near Mint; review the image.",
                "item_specifics": {"Game": "One Piece Card Game"},
                "keywords": ["Luffy", "OP01-024"],
            },
            "category_suggestion": "Collectible Card Games",
            "price_amount": "12.34",
            "currency": "USD",
            "quantity": 1,
            "selected_pricing_observation_id": OBSERVATION_ID,
            "content_origin": "ai_generated",
            "prompt_version": LISTING_PROMPT_VERSION,
            "ai_model": "gpt-4.1-mini",
            "created_at": datetime(2026, 7, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 7, 1, tzinfo=UTC),
        }
    )


@pytest.fixture
def authenticated_client() -> Iterator[TestClient]:
    user = AuthenticatedUser(
        user_id=USER_ID,
        claims={"sub": str(USER_ID), "role": "authenticated"},
        access_token=ACCESS_TOKEN,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", f"/cards/{CARD_ID}/listing-drafts", {}),
        ("GET", f"/cards/{CARD_ID}/listing-drafts", None),
        ("GET", f"/listing-drafts/{DRAFT_ID}", None),
        ("PATCH", f"/listing-drafts/{DRAFT_ID}", {"title": "Updated"}),
    ],
)
def test_listing_endpoints_reject_anonymous(
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    with TestClient(app) as client:
        response = client.request(method, path, json=payload)

    assert response.status_code == 401


def test_create_ai_draft_discards_unverified_price_and_creates_audit(
    authenticated_client: TestClient,
    draft_response: ListingDraftResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeListingRepository(draft_response)
    pricing = FakePricingRepository()
    audit = FakeAuditRepository()
    images = FakeImageStorage()
    generation = FakeGenerationService()
    monkeypatch.setattr(listing_api, "get_listing_repository", lambda: repository)
    monkeypatch.setattr(listing_api, "get_pricing_repository", lambda: pricing)
    monkeypatch.setattr(listing_api, "get_audit_repository", lambda: audit)
    monkeypatch.setattr(listing_api, "get_image_storage", lambda: images)
    monkeypatch.setattr(
        listing_api,
        "get_listing_generation_service",
        lambda: generation,
    )

    response = authenticated_client.post(
        f"/cards/{CARD_ID}/listing-drafts",
        json={},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Monkey D. Luffy OP01-024 Rare"
    assert response.json()["version"] == 1
    assert response.json()["ai_model"] == "gpt-4.1-mini"
    assert response.json()["prompt_version"] == LISTING_PROMPT_VERSION
    assert response.json()["price_amount"] is None
    assert repository.card_checked == CARD_ID
    assert repository.created_input is not None
    assert repository.created_input.price_amount is None
    assert repository.created_observation_id is None
    assert pricing.calls == []
    assert generation.calls[0]["image"] == images.image
    assert audit.events[0]["action"] == "listing_draft.created"
    assert audit.events[0]["draft_id"] == DRAFT_ID


def test_list_and_get_drafts(
    authenticated_client: TestClient,
    draft_response: ListingDraftResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeListingRepository(draft_response)
    monkeypatch.setattr(listing_api, "get_listing_repository", lambda: repository)

    list_response = authenticated_client.get(f"/cards/{CARD_ID}/listing-drafts")
    get_response = authenticated_client.get(f"/listing-drafts/{DRAFT_ID}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == str(DRAFT_ID)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == str(DRAFT_ID)


def test_update_draft_persists_version_and_audit(
    authenticated_client: TestClient,
    draft_response: ListingDraftResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeListingRepository(draft_response)
    pricing = FakePricingRepository()
    audit = FakeAuditRepository()
    monkeypatch.setattr(listing_api, "get_listing_repository", lambda: repository)
    monkeypatch.setattr(listing_api, "get_pricing_repository", lambda: pricing)
    monkeypatch.setattr(listing_api, "get_audit_repository", lambda: audit)

    response = authenticated_client.patch(
        f"/listing-drafts/{DRAFT_ID}",
        json={
            "title": "Reviewed placeholder",
            "item_specifics_json": {"Condition": "Near Mint"},
            "price_amount": "15.00",
            "currency": "USD",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Reviewed placeholder"
    assert response.json()["version"] == 2
    assert response.json()["price_amount"] == "15.00"
    assert repository.updated_observation_id == OBSERVATION_ID
    assert audit.events[0]["action"] == "listing_draft.updated"
    old_data = audit.events[0]["old_data"]
    new_data = audit.events[0]["new_data"]
    assert isinstance(old_data, dict)
    assert isinstance(new_data, dict)
    assert old_data["version"] == 1
    assert new_data["version"] == 2


@pytest.mark.parametrize("operation", ["create", "list", "get", "update"])
def test_cross_user_listing_access_returns_not_found(
    operation: str,
    authenticated_client: TestClient,
    draft_response: ListingDraftResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeListingRepository(draft_response)
    if operation in {"create", "list"}:
        repository.raise_on_card = ListingCardNotFoundError("Card not found")
    else:
        repository.raise_on_get = ListingDraftNotFoundError("Draft not found")
    monkeypatch.setattr(listing_api, "get_listing_repository", lambda: repository)
    monkeypatch.setattr(
        listing_api,
        "get_audit_repository",
        lambda: FakeAuditRepository(),
    )
    monkeypatch.setattr(listing_api, "get_image_storage", FakeImageStorage)
    monkeypatch.setattr(
        listing_api,
        "get_listing_generation_service",
        FakeGenerationService,
    )

    if operation == "create":
        response = authenticated_client.post(
            f"/cards/{CARD_ID}/listing-drafts",
            json={},
        )
    elif operation == "list":
        response = authenticated_client.get(f"/cards/{CARD_ID}/listing-drafts")
    elif operation == "get":
        response = authenticated_client.get(f"/listing-drafts/{DRAFT_ID}")
    else:
        response = authenticated_client.patch(
            f"/listing-drafts/{DRAFT_ID}",
            json={"title": "Forbidden"},
        )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 10},
        {"ai_model": "forged-model"},
        {"prompt_version": "forged-prompt"},
        {"price_amount": "10.00"},
        {"currency": "USD"},
    ],
)
def test_update_rejects_immutable_or_incomplete_fields(
    authenticated_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = authenticated_client.patch(
        f"/listing-drafts/{DRAFT_ID}",
        json=payload,
    )

    assert response.status_code == 422
