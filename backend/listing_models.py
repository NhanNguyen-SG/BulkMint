from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from card_models import CurrencyCode, PriceAmount

PLACEHOLDER_TEXT = "DRAFT PLACEHOLDER"
ListingDraftStatus = Literal["draft", "ready", "archived"]
DraftTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
DraftDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=10000),
]
CategorySuggestion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class ListingDraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_specifics_json: dict[str, Any] = Field(default_factory=dict)
    category_suggestion: CategorySuggestion | None = None
    price_amount: PriceAmount | None = None
    currency: CurrencyCode = "USD"

    def to_database_payload(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        selected_pricing_observation_id: UUID | None,
    ) -> dict[str, object]:
        return {
            "owner_id": str(owner_id),
            "card_id": str(card_id),
            "marketplace_target": "ebay",
            "status": "draft",
            "title": PLACEHOLDER_TEXT,
            "description": PLACEHOLDER_TEXT,
            "item_specifics_json": self.item_specifics_json,
            "category_suggestion": self.category_suggestion,
            "price_amount": (
                float(self.price_amount) if self.price_amount is not None else None
            ),
            "currency": self.currency,
            "quantity": 1,
            "selected_pricing_observation_id": (
                str(selected_pricing_observation_id)
                if selected_pricing_observation_id is not None
                else None
            ),
            "content_origin": "manual",
        }


class ListingDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ListingDraftStatus | None = None
    title: DraftTitle | None = None
    description: DraftDescription | None = None
    item_specifics_json: dict[str, Any] | None = None
    category_suggestion: CategorySuggestion | None = None
    price_amount: PriceAmount | None = None
    currency: CurrencyCode | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "ListingDraftUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")

        nullable_fields = {"category_suggestion"}
        for field_name in self.model_fields_set - nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        price_fields = {"price_amount", "currency"}
        supplied_price_fields = self.model_fields_set & price_fields
        if supplied_price_fields and supplied_price_fields != price_fields:
            raise ValueError("price_amount and currency must be updated together")

        return self

    @property
    def changes_price(self) -> bool:
        return "price_amount" in self.model_fields_set

    def to_database_payload(
        self,
        *,
        selected_pricing_observation_id: UUID | None = None,
    ) -> dict[str, object]:
        payload = self.model_dump(exclude_unset=True)

        if self.changes_price:
            if self.price_amount is None or selected_pricing_observation_id is None:
                raise ValueError("A price update requires a pricing observation")
            payload["price_amount"] = float(self.price_amount)
            payload["selected_pricing_observation_id"] = str(
                selected_pricing_observation_id
            )

        if self.status == "ready":
            payload["ready_at"] = datetime.now(UTC).isoformat()
        elif self.status == "archived":
            payload["archived_at"] = datetime.now(UTC).isoformat()

        return payload


class ListingDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    card_id: UUID
    analysis_job_id: UUID | None = None
    marketplace_target: str
    version: int
    status: ListingDraftStatus
    title: str
    description: str
    item_specifics_json: dict[str, Any]
    category_suggestion: str | None = None
    price_amount: Decimal | None = None
    currency: CurrencyCode
    quantity: int
    selected_pricing_observation_id: UUID | None = None
    content_origin: str
    prompt_version: str | None = None
    ai_model: str | None = None
    created_at: datetime
    updated_at: datetime
    ready_at: datetime | None = None
    archived_at: datetime | None = None

    @classmethod
    def from_database_row(cls, row: object) -> "ListingDraftResponse":
        if not isinstance(row, dict):
            raise ValueError("Supabase returned a non-object listing draft row")

        return cls.model_validate(
            {
                "id": row.get("id"),
                "card_id": row.get("card_id"),
                "analysis_job_id": row.get("analysis_job_id"),
                "marketplace_target": row.get("marketplace_target"),
                "version": row.get("version"),
                "status": row.get("status"),
                "title": row.get("title"),
                "description": row.get("description"),
                "item_specifics_json": row.get("item_specifics_json") or {},
                "category_suggestion": row.get("category_suggestion"),
                "price_amount": row.get("price_amount"),
                "currency": row.get("currency"),
                "quantity": row.get("quantity"),
                "selected_pricing_observation_id": row.get(
                    "selected_pricing_observation_id"
                ),
                "content_origin": row.get("content_origin"),
                "prompt_version": row.get("prompt_version"),
                "ai_model": row.get("generation_model"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "ready_at": row.get("ready_at"),
                "archived_at": row.get("archived_at"),
            }
        )
