import json
from uuid import UUID

import httpx
import pytest

from audit_repository import SupabaseAuditRepository

USER_ID = UUID("60126172-dd3c-4669-b6b4-717763578f89")
DRAFT_ID = UUID("224028bb-39ca-4086-9781-fecb201615fa")


def test_repository_creates_trusted_listing_audit_event_with_legacy_jwt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/audit_events"
        assert request.headers["apikey"] == "test-secret-key"
        assert request.headers["authorization"] == "Bearer test-secret-key"
        payload = json.loads(request.content)
        assert payload["owner_id"] == str(USER_ID)
        assert payload["actor_id"] == str(USER_ID)
        assert payload["action"] == "listing_draft.created"
        assert payload["entity_type"] == "listing_draft"
        assert payload["entity_id"] == str(DRAFT_ID)
        assert payload["old_data"] is None
        assert payload["new_data"] == {"version": 1}
        return httpx.Response(201)

    repository = SupabaseAuditRepository(
        supabase_url="https://test-project.supabase.co",
        secret_key="test-secret-key",
        authorization_token="test-secret-key",
        transport=httpx.MockTransport(handler),
    )
    repository.create_listing_event(
        owner_id=USER_ID,
        actor_id=USER_ID,
        action="listing_draft.created",
        draft_id=DRAFT_ID,
        old_data=None,
        new_data={"version": 1},
    )


def test_repository_uses_opaque_secret_key_only_as_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "sb_secret_test"
        assert "authorization" not in request.headers
        return httpx.Response(201)

    repository = SupabaseAuditRepository(
        supabase_url="https://test-project.supabase.co",
        secret_key="sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    repository.create_listing_event(
        owner_id=USER_ID,
        actor_id=USER_ID,
        action="listing_draft.created",
        draft_id=DRAFT_ID,
        old_data=None,
        new_data={"version": 1},
    )


def test_environment_prefers_opaque_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-service-role")

    repository = SupabaseAuditRepository.from_environment()

    assert repository.secret_key == "sb_secret_test"
    assert repository.authorization_token is None


def test_environment_preserves_legacy_service_role_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-service-role")

    repository = SupabaseAuditRepository.from_environment()

    assert repository.secret_key == "legacy-service-role"
    assert repository.authorization_token == "legacy-service-role"
