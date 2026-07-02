import os
from functools import lru_cache
from uuid import UUID

import httpx


class AuditRepositoryConfigurationError(RuntimeError):
    """Raised when trusted audit persistence is not configured."""


class AuditRepositoryError(RuntimeError):
    """Raised when Supabase cannot persist an audit event."""


class SupabaseAuditRepository:
    def __init__(
        self,
        *,
        supabase_url: str,
        secret_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.secret_key = secret_key
        self.transport = transport

    @classmethod
    def from_environment(cls) -> "SupabaseAuditRepository":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        secret_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY", ""
        )
        if not supabase_url:
            raise AuditRepositoryConfigurationError("SUPABASE_URL is required")
        if not secret_key:
            raise AuditRepositoryConfigurationError(
                "SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY is required"
            )
        return cls(supabase_url=supabase_url, secret_key=secret_key)

    def create_listing_event(
        self,
        *,
        owner_id: UUID,
        actor_id: UUID,
        action: str,
        draft_id: UUID,
        old_data: dict[str, object] | None,
        new_data: dict[str, object] | None,
    ) -> None:
        headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Prefer": "return=minimal",
        }
        try:
            with httpx.Client(
                base_url=self.supabase_url,
                timeout=10,
                transport=self.transport,
            ) as client:
                response = client.post(
                    "/rest/v1/audit_events",
                    headers=headers,
                    json={
                        "owner_id": str(owner_id),
                        "actor_id": str(actor_id),
                        "action": action,
                        "entity_type": "listing_draft",
                        "entity_id": str(draft_id),
                        "old_data": old_data,
                        "new_data": new_data,
                    },
                )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise AuditRepositoryError("Supabase audit request failed") from error


@lru_cache
def get_audit_repository() -> SupabaseAuditRepository:
    return SupabaseAuditRepository.from_environment()
