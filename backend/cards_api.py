from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError

from auth import AuthenticatedUser, get_current_user
from card_models import (
    CardCreate,
    CardResponse,
    CardStatus,
    CardUpdate,
    DetectedGame,
)
from cards_repository import (
    CardNotFoundError,
    CardsRepositoryConfigurationError,
    CardsRepositoryError,
    get_cards_repository,
)
from image_storage import (
    CARD_IMAGES_BUCKET,
    ImageStorageConfigurationError,
    ImageStorageDeletionError,
    ImageStorageError,
    ImageStoragePersistenceError,
    get_image_storage,
)
from image_validation import read_validated_image

router = APIRouter(prefix="/cards", tags=["cards"])


def repository_error(error: Exception) -> HTTPException:
    if isinstance(error, CardNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if isinstance(
        error,
        (CardsRepositoryConfigurationError, ImageStorageConfigurationError),
    ):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Card storage is not configured",
        )

    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Card storage request failed",
    )


def attach_card_images(
    *,
    cards: list[CardResponse],
    user: AuthenticatedUser,
) -> list[CardResponse]:
    images = get_image_storage().attach_signed_urls(
        cards=cards,
        owner_id=user.user_id,
        access_token=user.access_token,
    )
    return [
        card.model_copy(
            update={
                "image_id": images[card.id][0],
                "image_url": images[card.id][1],
            }
        )
        if card.id in images
        else card
        for card in cards
    ]


@router.get("", response_model=list[CardResponse])
def list_cards(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    card_status: Annotated[CardStatus | None, Query(alias="status")] = None,
    set_name: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    rarity: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    detected_game: Annotated[DetectedGame | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[CardResponse]:
    try:
        cards = get_cards_repository().list_cards(
            owner_id=user.user_id,
            access_token=user.access_token,
            q=q,
            status=card_status,
            set_name=set_name,
            rarity=rarity,
            detected_game=detected_game,
            limit=limit,
        )
        cards = attach_card_images(cards=cards, user=user)
    except (
        CardNotFoundError,
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
        ImageStorageError,
    ) as error:
        raise repository_error(error) from error

    return cards


@router.patch("/{card_id}/archive", response_model=CardResponse)
def archive_card(
    card_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CardResponse:
    try:
        archived_card = get_cards_repository().update_card(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
            card_update=CardUpdate(status="archived"),
        )
        return attach_card_images(cards=[archived_card], user=user)[0]
    except (
        CardNotFoundError,
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
        ImageStorageError,
    ) as error:
        raise repository_error(error) from error


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    try:
        image_storage = get_image_storage()
        repository = get_cards_repository()
        image_storage.delete_card_images(
            owner_id=user.user_id,
            card_id=card_id,
            access_token=user.access_token,
        )
        repository.delete_card(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
        )
    except (
        CardNotFoundError,
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
        ImageStorageDeletionError,
        ImageStorageError,
    ) as error:
        raise repository_error(error) from error


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    card_json: Annotated[str, Form(alias="card")],
    image: Annotated[UploadFile | None, File()] = None,
) -> CardResponse:
    try:
        card = CardCreate.model_validate_json(card_json)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid card payload",
        ) from error

    validated_image = await read_validated_image(image) if image is not None else None

    try:
        repository = get_cards_repository()
        image_storage = get_image_storage() if validated_image is not None else None
        created_card = repository.create_card(
            owner_id=user.user_id,
            access_token=user.access_token,
            card=card,
        )
    except (
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
    ) as error:
        raise repository_error(error) from error

    if validated_image is None or image_storage is None:
        return created_card

    try:
        stored_image = image_storage.persist_card_image(
            owner_id=user.user_id,
            card_id=created_card.id,
            access_token=user.access_token,
            image=validated_image,
        )
    except ImageStoragePersistenceError as error:
        if error.cleanup_complete:
            try:
                repository.delete_card(
                    owner_id=user.user_id,
                    access_token=user.access_token,
                    card_id=created_card.id,
                )
            except CardsRepositoryError as cleanup_error:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Image save failed and card cleanup is incomplete",
                ) from cleanup_error
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image save failed",
        ) from error

    try:
        image_url = image_storage.create_signed_url(
            bucket=CARD_IMAGES_BUCKET,
            storage_path=stored_image.storage_path,
            access_token=user.access_token,
        )
    except ImageStorageError:
        image_url = None

    return created_card.model_copy(
        update={
            "image_id": stored_image.image_id,
            "image_url": image_url,
        }
    )


@router.patch("/{card_id}", response_model=CardResponse)
def update_card(
    card_id: UUID,
    card_update: CardUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CardResponse:
    try:
        updated_card = get_cards_repository().update_card(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
            card_update=card_update,
        )
        return attach_card_images(cards=[updated_card], user=user)[0]
    except (
        CardNotFoundError,
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
        ImageStorageError,
    ) as error:
        raise repository_error(error) from error
