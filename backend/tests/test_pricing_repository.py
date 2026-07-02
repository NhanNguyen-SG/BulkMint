import json
from decimal import Decimal
from uuid import UUID

import httpx

from pricing_repository import MANUAL_LISTING_SOURCE, SupabasePricingRepository

USER_ID = UUID("18617161-9634-4465-9219-c2b05ff9a511")
CARD_ID = UUID("5c58d6fb-aa07-4949-bbaa-10476751c4f6")
SOURCE_ID = UUID("e9195f21-2553-44d7-887d-33600ca734c6")
OBSERVATION_ID = UUID("f4673c34-c183-486e-8f52-47b684f163f2")
ACCESS_TOKEN = "pricing-test-token"


def test_repository_creates_manual_price_provenance() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"

        if request.method == "GET":
            assert request.url.path == "/rest/v1/pricing_sources"
            assert request.url.params["owner_id"] == f"eq.{USER_ID}"
            assert request.url.params["source_type"] == "eq.manual"
            return httpx.Response(200, json=[])

        payload = json.loads(request.content)
        if request.url.path == "/rest/v1/pricing_sources":
            assert payload == {
                "owner_id": str(USER_ID),
                "source_type": "manual",
                "source_name": MANUAL_LISTING_SOURCE,
            }
            return httpx.Response(201, json=[{"id": str(SOURCE_ID)}])

        assert request.url.path == "/rest/v1/pricing_observations"
        assert payload["owner_id"] == str(USER_ID)
        assert payload["card_id"] == str(CARD_ID)
        assert payload["pricing_source_id"] == str(SOURCE_ID)
        assert payload["price_kind"] == "manual_override"
        assert payload["observed_price"] == 12.34
        assert payload["currency"] == "USD"
        assert payload["observed_at"]
        return httpx.Response(201, json=[{"id": str(OBSERVATION_ID)}])

    repository = SupabasePricingRepository(
        supabase_url="https://test-project.supabase.co",
        publishable_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    observation_id = repository.create_manual_observation(
        owner_id=USER_ID,
        access_token=ACCESS_TOKEN,
        card_id=CARD_ID,
        price_amount=Decimal("12.34"),
        currency="USD",
    )

    assert observation_id == OBSERVATION_ID
    assert len(requests) == 3
