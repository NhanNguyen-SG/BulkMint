import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from card_models import CardCreate, CardUpdate
from cards_repository import CardNotFoundError, SupabaseCardsRepository

USER_ID = UUID("c03d31fd-fe2e-45f8-8df3-fc6a1a4927bf")
CARD_ID = UUID("089c94e8-489a-4f87-a1ee-80f25c3f4b34")
ACCESS_TOKEN = "test-user-access-token"
CARD_PAYLOAD = {
    "card_name": "Roronoa Zoro",
    "set": "Romance Dawn",
    "card_number": "OP01-025",
    "rarity": "Rare",
    "condition_guess": "Near Mint",
    "suggested_price": "$8.00",
    "ebay_title": "Roronoa Zoro OP01-025",
    "ebay_description": "One Piece trading card.",
}
DATABASE_ROW = {
    "id": str(CARD_ID),
    "created_at": datetime(2026, 7, 1, tzinfo=UTC).isoformat(),
    "card_name": CARD_PAYLOAD["card_name"],
    "set_name": CARD_PAYLOAD["set"],
    "card_number": CARD_PAYLOAD["card_number"],
    "rarity": CARD_PAYLOAD["rarity"],
    "condition_guess": CARD_PAYLOAD["condition_guess"],
    "price_amount": 8,
    "currency": "USD",
    "status": "draft",
}


def test_repository_lists_only_authenticated_owner_cards() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["apikey"] == "test-publishable-key"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.url.params["owner_id"] == f"eq.{USER_ID}"
        assert request.url.params["order"] == "created_at.desc"
        return httpx.Response(200, json=[DATABASE_ROW])

    repository = SupabaseCardsRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    cards = repository.list_cards(owner_id=USER_ID, access_token=ACCESS_TOKEN)

    assert len(cards) == 1
    assert cards[0].id == CARD_ID
    assert cards[0].set == CARD_PAYLOAD["set"]


def test_repository_attaches_owner_to_created_card() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["prefer"] == "return=representation"

        payload = json.loads(request.content)
        assert payload["owner_id"] == str(USER_ID)
        assert payload["set_name"] == CARD_PAYLOAD["set"]
        assert payload["price_amount"] == 8
        assert payload["currency"] == "USD"
        assert payload["status"] == "draft"
        assert "suggested_price" not in payload
        assert "ebay_title" not in payload
        assert "ebay_description" not in payload
        assert "owner_id" not in CARD_PAYLOAD
        return httpx.Response(201, json=[DATABASE_ROW])

    repository = SupabaseCardsRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    card = repository.create_card(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        card=CardCreate.model_validate(CARD_PAYLOAD),
    )

    assert card.id == CARD_ID


def test_repository_updates_only_authenticated_owner_cards() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"
        assert request.headers["prefer"] == "return=representation"
        assert request.url.params["id"] == f"eq.{CARD_ID}"
        assert request.url.params["owner_id"] == f"eq.{USER_ID}"

        payload = json.loads(request.content)
        assert payload == {
            "card_name": "Updated Zoro",
            "price_amount": 12.5,
            "currency": "USD",
            "status": "active",
        }
        return httpx.Response(
            200,
            json=[
                {
                    **DATABASE_ROW,
                    "card_name": "Updated Zoro",
                    "price_amount": 12.5,
                    "status": "active",
                }
            ],
        )

    repository = SupabaseCardsRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(handler),
    )

    card = repository.update_card(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        card_id=CARD_ID,
        card_update=CardUpdate.model_validate(
            {
                "card_name": "Updated Zoro",
                "price_amount": "12.50",
                "currency": "usd",
                "status": "active",
            }
        ),
    )

    assert card.card_name == "Updated Zoro"
    assert card.price_amount == Decimal("12.5")
    assert card.status == "active"


def test_repository_raises_not_found_when_update_matches_no_rows() -> None:
    repository = SupabaseCardsRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[])),
    )

    with pytest.raises(CardNotFoundError):
        repository.update_card(
            owner_id=USER_ID,
            access_token=ACCESS_TOKEN,
            card_id=CARD_ID,
            card_update=CardUpdate.model_validate({"card_name": "Missing card"}),
        )


def test_repository_delete_raises_not_found_when_delete_matches_no_rows() -> None:
    repository = SupabaseCardsRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-publishable-key",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[])),
    )

    with pytest.raises(CardNotFoundError):
        repository.delete_card(
            owner_id=USER_ID,
            access_token=ACCESS_TOKEN,
            card_id=CARD_ID,
        )
