import os
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from uuid import UUID

import httpx

MANUAL_LISTING_SOURCE = "BulkMint listing draft manual price"
AI_LISTING_SOURCE = "BulkMint AI listing estimate"


class PricingRepositoryConfigurationError(RuntimeError):
    """Raised when pricing persistence configuration is incomplete."""


class PricingRepositoryError(RuntimeError):
    """Raised when Supabase cannot complete a pricing operation."""


class SupabasePricingRepository:
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
    def from_environment(cls) -> "SupabasePricingRepository":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
            "SUPABASE_ANON_KEY", ""
        )
        if not supabase_url:
            raise PricingRepositoryConfigurationError("SUPABASE_URL is required")
        if not publishable_key:
            raise PricingRepositoryConfigurationError(
                "SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY is required"
            )
        return cls(supabase_url=supabase_url, publishable_key=publishable_key)

    def create_manual_observation(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
        price_amount: Decimal,
        currency: str,
    ) -> UUID:
        source_id = self._get_or_create_source(
            owner_id=owner_id,
            access_token=access_token,
            source_type="manual",
            source_name=MANUAL_LISTING_SOURCE,
        )
        response = self._request(
            "POST",
            "/rest/v1/pricing_observations",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            params={"select": "id"},
            json={
                "owner_id": str(owner_id),
                "card_id": str(card_id),
                "pricing_source_id": str(source_id),
                "price_kind": "manual_override",
                "observed_price": float(price_amount),
                "currency": currency,
                "observed_at": datetime.now(UTC).isoformat(),
            },
        )
        return self._parse_single_id(response, "pricing observation")

    def create_ai_estimate(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
        price_amount: Decimal,
        currency: str,
        condition: str,
        model: str,
        prompt_version: str,
    ) -> UUID:
        source_id = self._get_or_create_source(
            owner_id=owner_id,
            access_token=access_token,
            source_type="ai",
            source_name=AI_LISTING_SOURCE,
        )
        response = self._request(
            "POST",
            "/rest/v1/pricing_observations",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            params={"select": "id"},
            json={
                "owner_id": str(owner_id),
                "card_id": str(card_id),
                "pricing_source_id": str(source_id),
                "price_kind": "estimate",
                "observed_price": float(price_amount),
                "currency": currency,
                "condition": condition,
                "observed_at": datetime.now(UTC).isoformat(),
                "generation_provider": "openai",
                "generation_model": model,
                "prompt_version": prompt_version,
            },
        )
        return self._parse_single_id(response, "pricing observation")

    def _get_or_create_source(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        source_type: str,
        source_name: str,
    ) -> UUID:
        response = self._request(
            "GET",
            "/rest/v1/pricing_sources",
            access_token=access_token,
            params={
                "select": "id",
                "owner_id": f"eq.{owner_id}",
                "source_type": f"eq.{source_type}",
                "source_name": f"eq.{source_name}",
                "limit": "1",
            },
        )
        rows = self._parse_rows(response)
        if rows:
            return self._row_id(rows[0], "pricing source")

        response = self._request(
            "POST",
            "/rest/v1/pricing_sources",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            params={"select": "id"},
            json={
                "owner_id": str(owner_id),
                "source_type": source_type,
                "source_name": source_name,
            },
        )
        return self._parse_single_id(response, "pricing source")

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
            raise PricingRepositoryError("Supabase pricing request failed") from error
        return response

    @staticmethod
    def _parse_rows(response: httpx.Response) -> list[object]:
        try:
            body = response.json()
        except ValueError as error:
            raise PricingRepositoryError("Supabase returned invalid pricing JSON") from error
        if not isinstance(body, list):
            raise PricingRepositoryError("Supabase pricing response is not a list")
        return body

    @classmethod
    def _parse_single_id(cls, response: httpx.Response, entity: str) -> UUID:
        rows = cls._parse_rows(response)
        if len(rows) != 1:
            raise PricingRepositoryError(
                f"Supabase did not return exactly one {entity}"
            )
        return cls._row_id(rows[0], entity)

    @staticmethod
    def _row_id(row: object, entity: str) -> UUID:
        if not isinstance(row, dict):
            raise PricingRepositoryError(f"Supabase returned an invalid {entity}")
        try:
            return UUID(str(row["id"]))
        except (KeyError, TypeError, ValueError) as error:
            raise PricingRepositoryError(
                f"Supabase returned an invalid {entity} ID"
            ) from error


@lru_cache
def get_pricing_repository() -> SupabasePricingRepository:
    return SupabasePricingRepository.from_environment()
