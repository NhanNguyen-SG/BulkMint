import os
from functools import lru_cache
from uuid import UUID

import httpx
from pydantic import ValidationError

from listing_models import (
    ListingDraftCreate,
    ListingDraftResponse,
    ListingDraftUpdate,
)

LISTING_DRAFT_COLUMNS = ",".join(
    (
        "id",
        "card_id",
        "analysis_job_id",
        "marketplace_target",
        "version",
        "status",
        "title",
        "description",
        "item_specifics_json",
        "category_suggestion",
        "price_amount",
        "currency",
        "quantity",
        "selected_pricing_observation_id",
        "content_origin",
        "prompt_version",
        "generation_model",
        "created_at",
        "updated_at",
        "ready_at",
        "archived_at",
    )
)


class ListingRepositoryConfigurationError(RuntimeError):
    """Raised when listing persistence configuration is incomplete."""


class ListingRepositoryError(RuntimeError):
    """Raised when Supabase cannot complete a listing operation."""


class ListingDraftNotFoundError(ListingRepositoryError):
    """Raised when a draft is missing or not owned by the caller."""


class ListingCardNotFoundError(ListingRepositoryError):
    """Raised when a parent card is missing or not owned by the caller."""


class SupabaseListingRepository:
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
    def from_environment(cls) -> "SupabaseListingRepository":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
            "SUPABASE_ANON_KEY", ""
        )
        if not supabase_url:
            raise ListingRepositoryConfigurationError("SUPABASE_URL is required")
        if not publishable_key:
            raise ListingRepositoryConfigurationError(
                "SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY is required"
            )
        return cls(supabase_url=supabase_url, publishable_key=publishable_key)

    def assert_card_owned(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> None:
        response = self._request(
            "GET",
            "/rest/v1/cards",
            access_token=access_token,
            params={
                "select": "id",
                "id": f"eq.{card_id}",
                "owner_id": f"eq.{owner_id}",
                "limit": "1",
            },
        )
        body = self._parse_list(response)
        if not body:
            raise ListingCardNotFoundError("Card not found")

    def create_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
        draft: ListingDraftCreate,
        selected_pricing_observation_id: UUID | None,
    ) -> ListingDraftResponse:
        response = self._request(
            "POST",
            "/rest/v1/listing_drafts",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            params={"select": LISTING_DRAFT_COLUMNS},
            json=draft.to_database_payload(
                owner_id=owner_id,
                card_id=card_id,
                selected_pricing_observation_id=selected_pricing_observation_id,
            ),
        )
        return self._parse_single_draft(response)

    def list_drafts(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        card_id: UUID,
    ) -> list[ListingDraftResponse]:
        response = self._request(
            "GET",
            "/rest/v1/listing_drafts",
            access_token=access_token,
            params={
                "select": LISTING_DRAFT_COLUMNS,
                "owner_id": f"eq.{owner_id}",
                "card_id": f"eq.{card_id}",
                "order": "created_at.desc",
                "limit": "100",
            },
        )
        return self._parse_drafts(response)

    def get_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        draft_id: UUID,
    ) -> ListingDraftResponse:
        response = self._request(
            "GET",
            "/rest/v1/listing_drafts",
            access_token=access_token,
            params={
                "select": LISTING_DRAFT_COLUMNS,
                "id": f"eq.{draft_id}",
                "owner_id": f"eq.{owner_id}",
                "limit": "1",
            },
        )
        drafts = self._parse_drafts(response)
        if not drafts:
            raise ListingDraftNotFoundError("Listing draft not found")
        return drafts[0]

    def update_draft(
        self,
        *,
        owner_id: UUID,
        access_token: str,
        draft_id: UUID,
        draft_update: ListingDraftUpdate,
        selected_pricing_observation_id: UUID | None = None,
    ) -> ListingDraftResponse:
        response = self._request(
            "PATCH",
            "/rest/v1/listing_drafts",
            access_token=access_token,
            headers={"Prefer": "return=representation"},
            params={
                "select": LISTING_DRAFT_COLUMNS,
                "id": f"eq.{draft_id}",
                "owner_id": f"eq.{owner_id}",
            },
            json=draft_update.to_database_payload(
                selected_pricing_observation_id=selected_pricing_observation_id
            ),
        )
        drafts = self._parse_drafts(response)
        if not drafts:
            raise ListingDraftNotFoundError("Listing draft not found")
        if len(drafts) != 1:
            raise ListingRepositoryError(
                "Supabase did not return exactly one updated listing draft"
            )
        return drafts[0]

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
            raise ListingRepositoryError("Supabase listing request failed") from error
        return response

    @staticmethod
    def _parse_list(response: httpx.Response) -> list[object]:
        try:
            body = response.json()
        except ValueError as error:
            raise ListingRepositoryError("Supabase returned invalid JSON") from error
        if not isinstance(body, list):
            raise ListingRepositoryError("Supabase response is not a list")
        return body

    @classmethod
    def _parse_drafts(cls, response: httpx.Response) -> list[ListingDraftResponse]:
        try:
            return [
                ListingDraftResponse.from_database_row(row)
                for row in cls._parse_list(response)
            ]
        except (ValueError, ValidationError) as error:
            raise ListingRepositoryError(
                "Supabase returned an invalid listing draft"
            ) from error

    @classmethod
    def _parse_single_draft(cls, response: httpx.Response) -> ListingDraftResponse:
        drafts = cls._parse_drafts(response)
        if len(drafts) != 1:
            raise ListingRepositoryError(
                "Supabase did not return exactly one created listing draft"
            )
        return drafts[0]


@lru_cache
def get_listing_repository() -> SupabaseListingRepository:
    return SupabaseListingRepository.from_environment()
