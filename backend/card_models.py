import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import BaseModel, ConfigDict

PRICE_PATTERN = re.compile(r"\d[\d,]*(?:\.\d{1,2})?")


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

    card_name: str
    set: str
    card_number: str
    rarity: str
    condition_guess: str
    suggested_price: str
    ebay_title: str
    ebay_description: str

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
                "suggested_price": display_price(
                    row.get("price_amount"),
                    row.get("currency"),
                ),
                # Listing persistence is deliberately outside Phase 4.
                "ebay_title": "",
                "ebay_description": "",
            }
        )
