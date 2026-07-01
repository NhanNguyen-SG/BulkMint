from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from auth import AuthenticatedUser, get_current_user
from card_models import CardCreate, CardResponse
from cards_repository import (
    CardsRepositoryConfigurationError,
    CardsRepositoryError,
    get_cards_repository,
)
from image_storage import (
    CARD_IMAGES_BUCKET,
    ImageStorageConfigurationError,
    ImageStorageError,
    ImageStoragePersistenceError,
    get_image_storage,
)
from image_validation import read_validated_image

router = APIRouter(prefix="/cards", tags=["cards"])


def repository_error(error: Exception) -> HTTPException:
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


@router.get("", response_model=list[CardResponse])
def list_cards(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[CardResponse]:
    try:
        cards = get_cards_repository().list_cards(
            owner_id=user.user_id,
            access_token=user.access_token,
        )
        images = get_image_storage().attach_signed_urls(
            cards=cards,
            owner_id=user.user_id,
            access_token=user.access_token,
        )
    except (
        CardsRepositoryConfigurationError,
        CardsRepositoryError,
        ImageStorageConfigurationError,
        ImageStorageError,
    ) as error:
        raise repository_error(error) from error

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
