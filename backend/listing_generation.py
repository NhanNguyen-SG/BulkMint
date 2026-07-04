import base64
import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Protocol, cast

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from card_models import CurrencyCode
from image_storage import CardImageForGeneration
from listing_models import ListingDraftCreate
from listing_repository import ListingCardContext

LISTING_PROMPT_VERSION = "listing-draft-v2"
DEFAULT_LISTING_MODEL = "gpt-4.1-mini"

LISTING_GENERATION_PROMPT = """
You create a private, review-only marketplace listing draft for one trading card.
This is not a publication action and you must not claim that anything was published.

Use only the saved card data and optional image supplied by the application.
Do not invent grading, authentication, provenance, edition, language, condition
details, or marketplace research that the inputs do not support.

Requirements:
- Produce a concise marketplace title no longer than 80 characters.
- Produce a factual seller-friendly description.
- Treat the saved condition as an estimate and write a cautious condition summary.
- Suggest a broad review-only category, not a marketplace category ID.
- Return item specifics only when supported by the inputs.
- Return useful search keywords without repetition or keyword stuffing.
- Never estimate, infer, or invent a price from card identity, rarity, condition,
  saved inventory values, or general model knowledge.
- Return a price only when the application explicitly supplies
  `verified_market_data` with supporting market observations.
- When `verified_market_data` is null or absent, `price_suggestion` and `currency`
  must both be null.
- Never include credentials, URLs, markdown, HTML, or publication instructions.
""".strip()

GeneratedTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
GeneratedDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
GeneratedCondition = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
GeneratedCategory = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
GeneratedSpecificName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
GeneratedSpecificValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
GeneratedKeyword = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
GeneratedPrice = Annotated[float, Field(ge=0, le=9_999_999_999.99)]


class GeneratedItemSpecific(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GeneratedSpecificName
    value: GeneratedSpecificValue


class GeneratedListingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: GeneratedTitle
    description: GeneratedDescription
    condition_summary: GeneratedCondition
    category_suggestion: GeneratedCategory
    item_specifics: list[GeneratedItemSpecific] = Field(max_length=20)
    keywords: list[GeneratedKeyword] = Field(min_length=1, max_length=15)
    price_suggestion: GeneratedPrice | None = None
    currency: CurrencyCode | None = None

    @model_validator(mode="after")
    def validate_generated_listing(self) -> "GeneratedListingDraft":
        specific_names = [specific.name.casefold() for specific in self.item_specifics]
        if len(specific_names) != len(set(specific_names)):
            raise ValueError("Generated item-specific names must be unique")

        normalized_keywords = [keyword.casefold() for keyword in self.keywords]
        if len(normalized_keywords) != len(set(normalized_keywords)):
            raise ValueError("Generated keywords must be unique")

        if (self.price_suggestion is None) != (self.currency is None):
            raise ValueError("Generated price and currency must both be set or null")
        return self

    def to_listing_draft(
        self,
        *,
        model: str,
        fallback_currency: str,
    ) -> ListingDraftCreate:
        item_specifics: dict[str, Any] = {
            "condition_summary": self.condition_summary,
            "item_specifics": {
                specific.name: specific.value for specific in self.item_specifics
            },
            "keywords": self.keywords,
        }
        return ListingDraftCreate(
            title=self.title,
            description=self.description,
            condition_summary=self.condition_summary,
            item_specifics_json=item_specifics,
            category_suggestion=self.category_suggestion,
            # The generation input currently contains no verified market evidence.
            # Model-supplied prices are therefore deliberately discarded.
            price_amount=None,
            currency=fallback_currency,
            generation_model=model,
            prompt_version=LISTING_PROMPT_VERSION,
            generated_at=datetime.now(UTC),
        )


class ParsedResponse(Protocol):
    output_parsed: GeneratedListingDraft | None


class ResponsesAPI(Protocol):
    def parse(self, **kwargs: Any) -> ParsedResponse: ...


class OpenAIClient(Protocol):
    @property
    def responses(self) -> ResponsesAPI: ...


class ListingGenerationConfigurationError(RuntimeError):
    """Raised when listing generation is not configured."""


class ListingGenerationError(RuntimeError):
    """Raised when OpenAI cannot return a validated listing draft."""


class ListingGenerationService:
    def __init__(self, *, client: OpenAIClient, model: str) -> None:
        self.client = client
        self.model = model

    @classmethod
    def from_environment(cls) -> "ListingGenerationService":
        model = os.getenv("OPENAI_LISTING_MODEL", DEFAULT_LISTING_MODEL).strip()
        if not model:
            raise ListingGenerationConfigurationError(
                "OPENAI_LISTING_MODEL cannot be empty"
            )
        try:
            client = OpenAI()
        except OpenAIError as error:
            raise ListingGenerationConfigurationError(
                "OpenAI listing generation is not configured"
            ) from error
        return cls(client=cast(OpenAIClient, client), model=model)

    def generate(
        self,
        *,
        card: ListingCardContext,
        image: CardImageForGeneration | None,
    ) -> ListingDraftCreate:
        card_context = {
            "card_name": card.card_name,
            "set_name": card.set_name,
            "card_number": card.card_number,
            "rarity": card.rarity,
            "condition_guess": card.condition_guess,
            "verified_market_data": None,
            "display_currency": card.currency,
        }
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Create a structured listing draft from this saved card data:\n"
                    + json.dumps(card_context, sort_keys=True)
                ),
            }
        ]
        if image is not None:
            encoded_image = base64.b64encode(image.content).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": (
                        f"data:{image.content_type};base64,{encoded_image}"
                    ),
                    "detail": "high",
                }
            )

        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=LISTING_GENERATION_PROMPT,
                input=[{"role": "user", "content": content}],
                text_format=GeneratedListingDraft,
                max_output_tokens=1200,
                store=False,
            )
        except OpenAIError as error:
            raise ListingGenerationError("OpenAI listing generation failed") from error

        generated = response.output_parsed
        if generated is None:
            raise ListingGenerationError(
                "OpenAI returned no validated listing draft"
            )

        return generated.to_listing_draft(
            model=self.model,
            fallback_currency=card.currency,
        )


@lru_cache
def get_listing_generation_service() -> ListingGenerationService:
    return ListingGenerationService.from_environment()
