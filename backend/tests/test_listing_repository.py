import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from listing_models import ListingDraftCreate, ListingDraftUpdate
from listing_repository import (
    ListingCardNotFoundError,
    ListingDraftNotFoundError,
    SupabaseListingRepository,
)

USER_ID = UUID("66304841-3a64-47cb-90c2-bb1d61c4c914")
CARD_ID = UUID("4d873406-0c21-4e24-a74a-63b51a1be21d")
DRAFT_ID = UUID("c05f66d0-1e65-4d13-8664-231e725f81f5")
OBSERVATION_ID = UUID("6b63e413-d3ca-450a-886c-574457e7b5eb")
ACCESS_TOKEN = "repository-listing-token"
NOW = datetime(2026, 7, 1, tzinfo=UTC).isoformat()
DRAFT_ROW = {
    "id": str(DRAFT_ID),
    "card_id": str(CARD_ID),
    "analysis_job_id": None,
    "marketplace_target": "ebay",
    "version": 1,
    "status": "draft",
    "title": "DRAFT PLACEHOLDER",
    "description": "DRAFT PLACEHOLDER",
    "item_specifics_json": {"Game": "One Piece Card Game"},
    "category_suggestion": "Collectible Card Games",
    "price_amount": 12.34,
    "currency": "USD",
    "quantity": 1,
    "selected_pricing_observation_id": str(OBSERVATION_ID),
    "content_origin": "manual",
    "prompt_version": None,
    "generation_model": None,
    "created_at": NOW,
    "updated_at": NOW,
    "ready_at": None,
    "archived_at": None,
}


def test_repository_creates_owner_placeholder_draft() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/listing_drafts"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        payload = json.loads(request.content)
        assert payload["owner_id"] == str(USER_ID)
        assert payload["card_id"] == str(CARD_ID)
        assert payload["title"] == "DRAFT PLACEHOLDER"
        assert payload["description"] == "DRAFT PLACEHOLDER"
        assert payload["content_origin"] == "manual"
        assert payload["item_specifics_json"] == {"Game": "One Piece Card Game"}
        assert payload["selected_pricing_observation_id"] == str(OBSERVATION_ID)
        assert "version" not in payload
        assert "generation_model" not in payload
        return httpx.Response(201, json=[DRAFT_ROW])

    repository = SupabaseListingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    draft = repository.create_draft(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        card_id=CARD_ID,
        draft=ListingDraftCreate.model_validate(
            {
                "item_specifics_json": {"Game": "One Piece Card Game"},
                "category_suggestion": "Collectible Card Games",
                "price_amount": "12.34",
                "currency": "USD",
            }
        ),
        selected_pricing_observation_id=OBSERVATION_ID,
    )

    assert draft.id == DRAFT_ID
    assert draft.version == 1
    assert draft.ai_model is None


def test_repository_lists_only_owner_card_drafts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["owner_id"] == f"eq.{USER_ID}"
        assert request.url.params["card_id"] == f"eq.{CARD_ID}"
        assert request.url.params["order"] == "created_at.desc"
        assert request.url.params["limit"] == "100"
        return httpx.Response(200, json=[DRAFT_ROW])

    repository = SupabaseListingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    drafts = repository.list_drafts(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        card_id=CARD_ID,
    )

    assert [draft.id for draft in drafts] == [DRAFT_ID]


def test_repository_hides_cross_owner_parent_card() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/cards"
        assert request.url.params["owner_id"] == f"eq.{USER_ID}"
        assert request.url.params["id"] == f"eq.{CARD_ID}"
        return httpx.Response(200, json=[])

    repository = SupabaseListingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ListingCardNotFoundError):
        repository.assert_card_owned(
            owner_id=USER_ID,
            access_token=ACCESS_TOKEN,
            card_id=CARD_ID,
        )


def test_repository_gets_and_updates_owner_draft() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.params["owner_id"] == f"eq.{USER_ID}"
        assert request.url.params["id"] == f"eq.{DRAFT_ID}"
        if request.method == "GET":
            return httpx.Response(200, json=[DRAFT_ROW])

        payload = json.loads(request.content)
        assert payload["title"] == "Reviewed draft"
        assert payload["price_amount"] == 15
        assert payload["currency"] == "USD"
        assert payload["selected_pricing_observation_id"] == str(OBSERVATION_ID)
        return httpx.Response(
            200,
            json=[
                {
                    **DRAFT_ROW,
                    "version": 2,
                    "title": "Reviewed draft",
                    "price_amount": 15,
                }
            ],
        )

    repository = SupabaseListingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    found = repository.get_draft(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        draft_id=DRAFT_ID,
    )
    updated = repository.update_draft(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        draft_id=DRAFT_ID,
        draft_update=ListingDraftUpdate.model_validate(
            {
                "title": "Reviewed draft",
                "price_amount": "15.00",
                "currency": "USD",
            }
        ),
        selected_pricing_observation_id=OBSERVATION_ID,
    )

    assert found.version == 1
    assert updated.version == 2
    assert len(requests) == 2


def test_repository_returns_not_found_for_hidden_draft() -> None:
    repository = SupabaseListingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=[])
        ),
    )

    with pytest.raises(ListingDraftNotFoundError):
        repository.get_draft(
            owner_id=USER_ID,
            access_token=ACCESS_TOKEN,
            draft_id=DRAFT_ID,
        )
