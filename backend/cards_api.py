from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from auth import AuthenticatedUser, get_current_user
from card_models import CardCreate, CardResponse
from cards_repository import (
    CardsRepositoryConfigurationError,
    CardsRepositoryError,
    get_cards_repository,
)

router = APIRouter(prefix="/cards", tags=["cards"])


def repository_error(error: Exception) -> HTTPException:
    if isinstance(error, CardsRepositoryConfigurationError):
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
        return get_cards_repository().list_cards(
            owner_id=user.user_id,
            access_token=user.access_token,
        )
    except (CardsRepositoryConfigurationError, CardsRepositoryError) as error:
        raise repository_error(error) from error


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    card: CardCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CardResponse:
    try:
        return get_cards_repository().create_card(
            owner_id=user.user_id,
            access_token=user.access_token,
            card=card,
        )
    except (CardsRepositoryConfigurationError, CardsRepositoryError) as error:
        raise repository_error(error) from error
