from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from image_storage import CardImageForGeneration
from listing_generation import (
    LISTING_GENERATION_PROMPT,
    LISTING_PROMPT_VERSION,
    GeneratedListingDraft,
    ListingGenerationError,
    ListingGenerationService,
)
from listing_repository import ListingCardContext

CARD_ID = UUID("542f745d-b436-41d3-b763-5846782de6dc")


class FakeResponsesAPI:
    def __init__(self, output: GeneratedListingDraft | None) -> None:
        self.output = output
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output)


class FakeOpenAIClient:
    def __init__(self, output: GeneratedListingDraft | None) -> None:
        self.responses = FakeResponsesAPI(output)


@pytest.fixture
def card_context() -> ListingCardContext:
    return ListingCardContext(
        card_id=CARD_ID,
        detected_game="One Piece",
        card_name="Monkey D. Luffy",
        set_name="Romance Dawn",
        card_number="OP01-024",
        rarity="Rare",
        condition_guess="Near Mint",
        price_amount=Decimal("12.34"),
        currency="USD",
    )


@pytest.fixture
def generated_output() -> GeneratedListingDraft:
    return GeneratedListingDraft.model_validate(
        {
            "title": "Monkey D. Luffy OP01-024 Rare",
            "description": "Review-only draft based on the saved card details.",
            "condition_summary": "Appears Near Mint; verify the image before listing.",
            "category_suggestion": "Collectible Card Games",
            "item_specifics": [
                {"name": "Game", "value": "One Piece Card Game"},
                {"name": "Set", "value": "Romance Dawn"},
                {"name": "Card Number", "value": "OP01-024"},
            ],
            "keywords": ["Luffy", "OP01-024", "Romance Dawn"],
            "price_suggestion": "12.34",
            "currency": "USD",
        }
    )


def test_generate_uses_structured_output_card_data_and_image(
    card_context: ListingCardContext,
    generated_output: GeneratedListingDraft,
) -> None:
    client = FakeOpenAIClient(generated_output)
    service = ListingGenerationService(client=client, model="gpt-4.1-mini")
    image = CardImageForGeneration(
        content=b"image-bytes",
        content_type="image/png",
    )

    draft = service.generate(card=card_context, image=image)

    assert draft.title == generated_output.title
    assert draft.condition_summary == generated_output.condition_summary
    assert draft.item_specifics_json["keywords"] == generated_output.keywords
    assert draft.price_amount is None
    assert draft.currency == "USD"
    assert draft.generation_model == "gpt-4.1-mini"
    assert draft.prompt_version == LISTING_PROMPT_VERSION

    request = client.responses.calls[0]
    assert request["instructions"] == LISTING_GENERATION_PROMPT
    assert request["text_format"] is GeneratedListingDraft
    assert request["store"] is False
    input_items = request["input"][0]["content"]
    assert input_items[0]["type"] == "input_text"
    assert '"detected_game": "One Piece"' in input_items[0]["text"]
    assert "Monkey D. Luffy" in input_items[0]["text"]
    assert '"verified_market_data": null' in input_items[0]["text"]
    assert "saved_price_amount" not in input_items[0]["text"]
    assert input_items[1]["type"] == "input_image"
    assert input_items[1]["image_url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    "detected_game",
    ["Pokemon", "One Piece", "Magic: The Gathering", "Yu-Gi-Oh!"],
)
def test_generate_includes_representative_game_context(
    card_context: ListingCardContext,
    generated_output: GeneratedListingDraft,
    detected_game: str,
) -> None:
    client = FakeOpenAIClient(generated_output)
    service = ListingGenerationService(client=client, model="gpt-4.1-mini")
    game_card = ListingCardContext(
        card_id=card_context.card_id,
        detected_game=detected_game,
        card_name=card_context.card_name,
        set_name=card_context.set_name,
        card_number=card_context.card_number,
        rarity=card_context.rarity,
        condition_guess=card_context.condition_guess,
        price_amount=card_context.price_amount,
        currency=card_context.currency,
    )

    service.generate(card=game_card, image=None)

    input_text = client.responses.calls[0]["input"][0]["content"][0]["text"]
    assert f'"detected_game": "{detected_game}"' in input_text
    assert "Do not assume One Piece" in LISTING_GENERATION_PROMPT


def test_generated_price_fields_are_optional(
    generated_output: GeneratedListingDraft,
) -> None:
    payload = generated_output.model_dump()
    payload.pop("price_suggestion")
    payload.pop("currency")

    generated = GeneratedListingDraft.model_validate(payload)

    assert generated.price_suggestion is None
    assert generated.currency is None


def test_generate_without_image_uses_saved_card_data_only(
    card_context: ListingCardContext,
    generated_output: GeneratedListingDraft,
) -> None:
    client = FakeOpenAIClient(generated_output)
    service = ListingGenerationService(client=client, model="gpt-4.1-mini")

    service.generate(card=card_context, image=None)

    input_items = client.responses.calls[0]["input"][0]["content"]
    assert [item["type"] for item in input_items] == ["input_text"]


def test_generate_rejects_missing_parsed_output(
    card_context: ListingCardContext,
) -> None:
    service = ListingGenerationService(
        client=FakeOpenAIClient(None),
        model="gpt-4.1-mini",
    )

    with pytest.raises(ListingGenerationError):
        service.generate(card=card_context, image=None)


@pytest.mark.parametrize(
    "updates",
    [
        {"currency": None},
        {
            "item_specifics": [
                {"name": "Game", "value": "One Piece Card Game"},
                {"name": "game", "value": "Duplicate"},
            ]
        },
        {"keywords": ["Luffy", "luffy"]},
    ],
)
def test_structured_output_rejects_inconsistent_values(
    generated_output: GeneratedListingDraft,
    updates: dict[str, object],
) -> None:
    payload = generated_output.model_dump()
    payload.update(updates)

    with pytest.raises(ValidationError):
        GeneratedListingDraft.model_validate(payload)
