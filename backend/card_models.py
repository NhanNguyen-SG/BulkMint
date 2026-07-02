import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PRICE_PATTERN = re.compile(r"\d[\d,]*(?:\.\d{1,2})?")
CardStatus = Literal["draft", "active", "listed", "sold", "archived"]
CardName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
SetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
CardNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
CardRarity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ConditionGuess = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
PriceDisplay = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
EbayTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=120)
]
EbayDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=4000)
]
CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        pattern=r"^[A-Za-z]{3}$",
        min_length=3,
        max_length=3,
    ),
]
PriceAmount = Annotated[Decimal, Field(ge=Decimal("0"), max_digits=12, decimal_places=2)]


def parse_price(value: str) -> Decimal | None:
    match = PRICE_PATTERN.search(value)
    if match is None:
        return None

    try:
        return Decimal(match.group().replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def display_price(amount: object, currency: object) -> str:
    if amount is None:
        return "Unknown"

    try:
        normalized_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    except InvalidOperation as error:
        raise ValueError("Supabase returned an invalid card price") from error

    normalized_currency = str(currency or "USD").upper()
    if normalized_currency == "USD":
        return f"${normalized_amount}"

    return f"{normalized_amount} {normalized_currency}"


class CardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_name: CardName
    set: SetName
    card_number: CardNumber
    rarity: CardRarity
    condition_guess: ConditionGuess
    suggested_price: PriceDisplay
    ebay_title: EbayTitle
    ebay_description: EbayDescription

    def to_database_payload(self, owner_id: UUID) -> dict[str, object]:
        price_amount = parse_price(self.suggested_price)

        return {
            "owner_id": str(owner_id),
            "card_name": self.card_name,
            "set_name": self.set,
            "card_number": self.card_number,
            "rarity": self.rarity,
            "condition_guess": self.condition_guess,
            "price_amount": float(price_amount) if price_amount is not None else None,
            "currency": "USD",
            "status": "draft",
        }


class CardResponse(CardCreate):
    id: UUID
    created_at: datetime
    price_amount: Decimal | None = None
    currency: CurrencyCode = "USD"
    status: CardStatus = "draft"
    image_id: UUID | None = None
    image_url: str | None = None

    @classmethod
    def from_database_row(cls, row: object) -> "CardResponse":
        if not isinstance(row, dict):
            raise ValueError("Supabase returned a non-object card row")

        return cls.model_validate(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "card_name": row.get("card_name"),
                "set": row.get("set_name"),
                "card_number": row.get("card_number"),
                "rarity": row.get("rarity"),
                "condition_guess": row.get("condition_guess"),
                "price_amount": row.get("price_amount"),
                "currency": row.get("currency") or "USD",
                "status": row.get("status") or "draft",
                "suggested_price": display_price(
                    row.get("price_amount"),
                    row.get("currency"),
                ),
                # Listing persistence is deliberately outside Phase 4.
                "ebay_title": "",
                "ebay_description": "",
            }
        )


class CardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_name: CardName | None = None
    set: SetName | None = None
    card_number: CardNumber | None = None
    rarity: CardRarity | None = None
    condition_guess: ConditionGuess | None = None
    price_amount: PriceAmount | None = None
    currency: CurrencyCode | None = None
    status: CardStatus | None = None

    @model_validator(mode="after")
    def validate_update_fields(self) -> "CardUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")

        for field_name in self.model_fields_set:
            if field_name != "price_amount" and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self

    def to_database_payload(self) -> dict[str, object]:
        payload = self.model_dump(exclude_unset=True)

        if "set" in payload:
            payload["set_name"] = payload.pop("set")
        if "price_amount" in payload and payload["price_amount"] is not None:
            payload["price_amount"] = float(payload["price_amount"])

        return payload
