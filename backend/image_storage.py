import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote, urljoin
from uuid import UUID, uuid4

import httpx

from card_models import CardResponse
from image_validation import ValidatedImage

CARD_IMAGES_BUCKET = "card-images"
SIGNED_URL_TTL_SECONDS = 300


class ImageStorageConfigurationError(RuntimeError):
    """Raised when the Supabase Storage configuration is incomplete."""


class ImageStorageError(RuntimeError):
    """Raised when card-image persistence or retrieval fails."""


class ImageStoragePersistenceError(ImageStorageError):
    def __init__(self, message: str, *, cleanup_complete: bool) -> None:
        super().__init__(message)
        self.cleanup_complete = cleanup_complete


class ImageStorageDeletionError(ImageStorageError):
    """Raised when card-image cleanup cannot be completed safely."""


@dataclass(frozen=True)
class StoredCardImage:
    image_id: UUID
    card_id: UUID
    storage_path: str


@dataclass(frozen=True)
class CardImageForGeneration:
    content: bytes
    content_type: str


class SupabaseImageStorage:
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
    def from_environment(cls) -> "SupabaseImageStorage":
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
            "SUPABASE_ANON_KEY", ""
        )

        if not supabase_url:
            raise ImageStorageConfigurationError("SUPABASE_URL is required")
        if not publishable_key:
            raise ImageStorageConfigurationError(
                "SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY is required"
            )

        return cls(
            supabase_url=supabase_url,
            publishable_key=publishable_key,
        )

    def persist_card_image(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
        image: ValidatedImage,
    ) -> StoredCardImage:
        image_id = uuid4()
        storage_path = f"{owner_id}/{card_id}/{image_id}.{image.extension}"
        metadata_created = False
        upload_attempted = False

        try:
            self._insert_pending_metadata(
                owner_id=owner_id,
                card_id=card_id,
                image_id=image_id,
                storage_path=storage_path,
                access_token=access_token,
                image=image,
            )
            metadata_created = True
            upload_attempted = True
            self._upload_object(
                storage_path=storage_path,
                access_token=access_token,
                image=image,
            )
            self._activate_metadata(
                image_id=image_id,
                owner_id=owner_id,
                access_token=access_token,
            )
        except ImageStorageError as error:
            cleanup_complete = self._compensate_failed_persistence(
                image_id=image_id,
                owner_id=owner_id,
                storage_path=storage_path,
                access_token=access_token,
                metadata_created=metadata_created,
                upload_attempted=upload_attempted,
            )
            raise ImageStoragePersistenceError(
                "Card image persistence failed",
                cleanup_complete=cleanup_complete,
            ) from error

        return StoredCardImage(
            image_id=image_id,
            card_id=card_id,
            storage_path=storage_path,
        )

    def attach_signed_urls(
        self,
        *,
        cards: list[CardResponse],
        owner_id: UUID,
        access_token: str,
    ) -> dict[UUID, tuple[UUID, str]]:
        card_ids = [card.id for card in cards]
        if not card_ids:
            return {}

        response = self._request(
            "GET",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "select": "id,card_id,storage_bucket,storage_path",
                "owner_id": f"eq.{owner_id}",
                "card_id": f"in.({','.join(str(card_id) for card_id in card_ids)})",
                "status": "eq.active",
                "order": "created_at.desc",
            },
        )

        body = self._json(response)
        if not isinstance(body, list):
            raise ImageStorageError("Supabase returned invalid image metadata")

        images_by_card: dict[UUID, tuple[UUID, str]] = {}
        for row in body:
            if not isinstance(row, dict):
                raise ImageStorageError("Supabase returned invalid image metadata")

            try:
                image_id = UUID(str(row["id"]))
                card_id = UUID(str(row["card_id"]))
                bucket = str(row["storage_bucket"])
                storage_path = str(row["storage_path"])
            except (KeyError, TypeError, ValueError) as error:
                raise ImageStorageError("Supabase returned invalid image metadata") from error

            if card_id in images_by_card:
                continue

            signed_url = self.create_signed_url(
                bucket=bucket,
                storage_path=storage_path,
                access_token=access_token,
            )
            images_by_card[card_id] = (image_id, signed_url)

        return images_by_card

    def get_card_image_for_generation(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
    ) -> CardImageForGeneration | None:
        response = self._request(
            "GET",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "select": "storage_bucket,storage_path,mime_type",
                "owner_id": f"eq.{owner_id}",
                "card_id": f"eq.{card_id}",
                "status": "eq.active",
                "image_kind": "eq.front",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        body = self._json(response)
        if not isinstance(body, list):
            raise ImageStorageError("Supabase returned invalid image metadata")
        if not body:
            return None

        row = body[0]
        if not isinstance(row, dict):
            raise ImageStorageError("Supabase returned invalid image metadata")
        try:
            bucket = str(row["storage_bucket"])
            storage_path = str(row["storage_path"])
            content_type = str(row["mime_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise ImageStorageError("Supabase returned invalid image metadata") from error

        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ImageStorageError("Card image has an unsupported MIME type")

        encoded_path = quote(storage_path, safe="/")
        image_response = self._request(
            "GET",
            f"/storage/v1/object/authenticated/{bucket}/{encoded_path}",
            access_token=access_token,
        )
        if not image_response.content:
            raise ImageStorageError("Stored card image is empty")
        return CardImageForGeneration(
            content=image_response.content,
            content_type=content_type,
        )

    def create_signed_url(
        self,
        *,
        bucket: str,
        storage_path: str,
        access_token: str,
    ) -> str:
        encoded_path = quote(storage_path, safe="/")
        response = self._request(
            "POST",
            f"/storage/v1/object/sign/{bucket}/{encoded_path}",
            access_token=access_token,
            json={"expiresIn": SIGNED_URL_TTL_SECONDS},
        )
        body = self._json(response)
        if not isinstance(body, dict):
            raise ImageStorageError("Supabase returned an invalid signed URL response")

        signed_url = body.get("signedURL") or body.get("signedUrl")
        if not isinstance(signed_url, str) or not signed_url:
            raise ImageStorageError("Supabase returned no signed URL")

        if signed_url.startswith("/object/"):
            signed_url = f"/storage/v1{signed_url}"

        return urljoin(f"{self.supabase_url}/", signed_url)

    def delete_card_images(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
    ) -> None:
        for stored_image in self._list_card_images(
            owner_id=owner_id,
            card_id=card_id,
            access_token=access_token,
        ):
            try:
                self._delete_object(
                    storage_path=stored_image.storage_path,
                    access_token=access_token,
                    allow_missing=True,
                )
                self._delete_metadata(
                    image_id=stored_image.image_id,
                    owner_id=owner_id,
                    access_token=access_token,
                )
            except ImageStorageError as error:
                try:
                    self._mark_metadata_failed(
                        image_id=stored_image.image_id,
                        owner_id=owner_id,
                        access_token=access_token,
                    )
                except ImageStorageError:
                    pass
                raise ImageStorageDeletionError("Card image cleanup failed") from error

    def _list_card_images(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        access_token: str,
    ) -> list[StoredCardImage]:
        response = self._request(
            "GET",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "select": "id,card_id,storage_path",
                "owner_id": f"eq.{owner_id}",
                "card_id": f"eq.{card_id}",
                "order": "created_at.desc",
            },
        )
        body = self._json(response)
        if not isinstance(body, list):
            raise ImageStorageError("Supabase returned invalid image metadata")

        images: list[StoredCardImage] = []
        for row in body:
            if not isinstance(row, dict):
                raise ImageStorageError("Supabase returned invalid image metadata")

            try:
                images.append(
                    StoredCardImage(
                        image_id=UUID(str(row["id"])),
                        card_id=UUID(str(row["card_id"])),
                        storage_path=str(row["storage_path"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ImageStorageError("Supabase returned invalid image metadata") from error

        return images

    def _insert_pending_metadata(
        self,
        *,
        owner_id: UUID,
        card_id: UUID,
        image_id: UUID,
        storage_path: str,
        access_token: str,
        image: ValidatedImage,
    ) -> None:
        self._request(
            "POST",
            "/rest/v1/card_images",
            access_token=access_token,
            headers={"Prefer": "return=minimal"},
            json={
                "id": str(image_id),
                "owner_id": str(owner_id),
                "card_id": str(card_id),
                "storage_bucket": CARD_IMAGES_BUCKET,
                "storage_path": storage_path,
                "image_kind": "front",
                "mime_type": image.content_type,
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "status": "pending",
            },
        )

    def _upload_object(
        self,
        *,
        storage_path: str,
        access_token: str,
        image: ValidatedImage,
    ) -> None:
        encoded_path = quote(storage_path, safe="/")
        self._request(
            "POST",
            f"/storage/v1/object/{CARD_IMAGES_BUCKET}/{encoded_path}",
            access_token=access_token,
            headers={
                "Content-Type": image.content_type,
                "x-upsert": "false",
            },
            content=image.content,
        )

    def _activate_metadata(
        self,
        *,
        image_id: UUID,
        owner_id: UUID,
        access_token: str,
    ) -> None:
        self._request(
            "PATCH",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "id": f"eq.{image_id}",
                "owner_id": f"eq.{owner_id}",
            },
            json={"status": "active"},
        )

    def _delete_object(
        self,
        *,
        storage_path: str,
        access_token: str,
        allow_missing: bool = False,
    ) -> None:
        encoded_path = quote(storage_path, safe="/")
        try:
            self._request(
                "DELETE",
                f"/storage/v1/object/{CARD_IMAGES_BUCKET}/{encoded_path}",
                access_token=access_token,
            )
        except ImageStorageError as error:
            if allow_missing and self._is_not_found_error(error):
                return
            raise

    def _delete_metadata(
        self,
        *,
        image_id: UUID,
        owner_id: UUID,
        access_token: str,
    ) -> None:
        self._request(
            "DELETE",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "id": f"eq.{image_id}",
                "owner_id": f"eq.{owner_id}",
            },
        )

    def _mark_metadata_failed(
        self,
        *,
        image_id: UUID,
        owner_id: UUID,
        access_token: str,
    ) -> None:
        self._request(
            "PATCH",
            "/rest/v1/card_images",
            access_token=access_token,
            params={
                "id": f"eq.{image_id}",
                "owner_id": f"eq.{owner_id}",
            },
            json={"status": "failed"},
        )

    def _compensate_failed_persistence(
        self,
        *,
        image_id: UUID,
        owner_id: UUID,
        storage_path: str,
        access_token: str,
        metadata_created: bool,
        upload_attempted: bool,
    ) -> bool:
        if not metadata_created:
            return True

        if upload_attempted:
            try:
                self._delete_object(
                    storage_path=storage_path,
                    access_token=access_token,
                )
            except ImageStorageError:
                try:
                    self._mark_metadata_failed(
                        image_id=image_id,
                        owner_id=owner_id,
                        access_token=access_token,
                    )
                except ImageStorageError:
                    pass
                return False

        try:
            self._delete_metadata(
                image_id=image_id,
                owner_id=owner_id,
                access_token=access_token,
            )
        except ImageStorageError:
            try:
                self._mark_metadata_failed(
                    image_id=image_id,
                    owner_id=owner_id,
                    access_token=access_token,
                )
            except ImageStorageError:
                pass
            return False

        return True

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        request_headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {access_token}",
            **(headers or {}),
        }

        try:
            with httpx.Client(
                base_url=self.supabase_url,
                timeout=15,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    headers=request_headers,
                    params=params,
                    json=json,
                    content=content,
                )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ImageStorageError("Supabase image request failed") from error

        return response

    @staticmethod
    def _json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as error:
            raise ImageStorageError("Supabase returned invalid JSON") from error

    @staticmethod
    def _is_not_found_error(error: ImageStorageError) -> bool:
        cause = error.__cause__
        if not isinstance(cause, httpx.HTTPStatusError):
            return False

        return cause.response.status_code == 404


@lru_cache
def get_image_storage() -> SupabaseImageStorage:
    return SupabaseImageStorage.from_environment()
