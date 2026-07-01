import os
from functools import lru_cache
from uuid import UUID

import httpx
from pydantic import ValidationError

from card_models import CardCreate, CardResponse

CARD_COLUMNS = ",".join(
    (
        "id",
        "created_at",
        "card_name",
        "set_name",
        "card_number",
        "rarity",
        "condition_guess",
        "price_amount",
        "currency",
        "status",
    )
)


class CardsRepositoryConfigurationError(RuntimeError):
    """Raised when the Supabase Data API configuration is incomplete."""


class CardsRepositoryError(RuntimeError):
    """Raised when Supabase cannot complete or validate a cards operation."""


class SupabaseCardsRepository:
    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.publishable_key = publishable_key
        self.transport = transport

    @classmethod
    def from_environment(cls) -> "SupabaseCardsRepository":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
            "SUPABASE_ANON_KEY", ""
        )

        if not supabase_url:
            raise CardsRepositoryConfigurationError("SUPABASE_URL is required")
        if not publishable_key:
            raise CardsRepositoryConfigurationError(
                "SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY is required"
            )

        return cls(
            supabase_url=supabase_url,
            publishable_key=publishable_key,
        )

    def list_cards(self, *, owner_id: UUID, access_token: str) -> list[CardResponse]:
        response = self._request(
            "GET",
            "/rest/v1/cards",
            access_token=access_token,
            params={
                "select": CARD_COLUMNS,
                "owner_id": f"eq.{owner_id}",
                "order": "created_at.desc",
            },
        )
        return self._parse_rows(response)

    def create_card(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card: CardCreate,
    ) -> CardResponse:
        response = self._request(
            "POST",
            "/rest/v1/cards",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            json=card.to_database_payload(owner_id),
            params={"select": CARD_COLUMNS},
        )
        rows = self._parse_rows(response)
        if len(rows) != 1:
            raise CardsRepositoryError("Supabase did not return exactly one created card")

        return rows[0]

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {access_token}",
            **(headers or {}),
        }

        try:
            with httpx.Client(
                base_url=self.supabase_url,
                timeout=10,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    headers=request_headers,
                    params=params,
                    json=json,
                )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise CardsRepositoryError("Supabase cards request failed") from error

        return response

    @staticmethod
    def _parse_rows(response: httpx.Response) -> list[CardResponse]:
        try:
            body = response.json()
            if not isinstance(body, list):
                raise ValueError("Supabase cards response is not a list")

            return [CardResponse.from_database_row(row) for row in body]
        except (ValueError, ValidationError) as error:
            raise CardsRepositoryError("Supabase returned an invalid cards response") from error


@lru_cache
def get_cards_repository() -> SupabaseCardsRepository:
    return SupabaseCardsRepository.from_environment()
