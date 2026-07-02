from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status

from audit_repository import (
    AuditRepositoryConfigurationError,
    AuditRepositoryError,
    get_audit_repository,
)
from auth import AuthenticatedUser, get_current_user
from listing_models import (
    ListingDraftCreate,
    ListingDraftResponse,
    ListingDraftUpdate,
)
from listing_repository import (
    ListingCardNotFoundError,
    ListingDraftNotFoundError,
    ListingRepositoryConfigurationError,
    ListingRepositoryError,
    get_listing_repository,
)
from pricing_repository import (
    PricingRepositoryConfigurationError,
    PricingRepositoryError,
    get_pricing_repository,
)

router = APIRouter(tags=["listing-drafts"])


def listing_error(error: Exception) -> HTTPException:
    if isinstance(error, ListingCardNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if isinstance(error, ListingDraftNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing draft not found",
        )
    if isinstance(
        error,
        (
            AuditRepositoryConfigurationError,
            ListingRepositoryConfigurationError,
            PricingRepositoryConfigurationError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Listing draft storage is not configured",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Listing draft storage request failed",
    )


def audit_data(draft: ListingDraftResponse) -> dict[str, object]:
    return draft.model_dump(mode="json")


@router.post(
    "/cards/{card_id}/listing-drafts",
    response_model=ListingDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_listing_draft(
    card_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    draft: Annotated[ListingDraftCreate, Body()] = ListingDraftCreate(),
) -> ListingDraftResponse:
    try:
        repository = get_listing_repository()
        audit_repository = get_audit_repository()
        repository.assert_card_owned(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
        )

        selected_observation_id = None
        if draft.price_amount is not None:
            selected_observation_id = (
                get_pricing_repository().create_manual_observation(
                    owner_id=user.user_id,
                    access_token=user.access_token,
                    card_id=card_id,
                    price_amount=draft.price_amount,
                    currency=draft.currency,
                )
            )

        created_draft = repository.create_draft(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
            draft=draft,
            selected_pricing_observation_id=selected_observation_id,
        )
        audit_repository.create_listing_event(
            owner_id=user.user_id,
            actor_id=user.user_id,
            action="listing_draft.created",
            draft_id=created_draft.id,
            old_data=None,
            new_data=audit_data(created_draft),
        )
        return created_draft
    except (
        AuditRepositoryConfigurationError,
        AuditRepositoryError,
        ListingCardNotFoundError,
        ListingDraftNotFoundError,
        ListingRepositoryConfigurationError,
        ListingRepositoryError,
        PricingRepositoryConfigurationError,
        PricingRepositoryError,
    ) as error:
        raise listing_error(error) from error


@router.get(
    "/cards/{card_id}/listing-drafts",
    response_model=list[ListingDraftResponse],
)
def list_listing_drafts(
    card_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[ListingDraftResponse]:
    try:
        repository = get_listing_repository()
        repository.assert_card_owned(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
        )
        return repository.list_drafts(
            owner_id=user.user_id,
            access_token=user.access_token,
            card_id=card_id,
        )
    except (
        ListingCardNotFoundError,
        ListingDraftNotFoundError,
        ListingRepositoryConfigurationError,
        ListingRepositoryError,
    ) as error:
        raise listing_error(error) from error


@router.get(
    "/listing-drafts/{draft_id}",
    response_model=ListingDraftResponse,
)
def get_listing_draft(
    draft_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ListingDraftResponse:
    try:
        return get_listing_repository().get_draft(
            owner_id=user.user_id,
            access_token=user.access_token,
            draft_id=draft_id,
        )
    except (
        ListingDraftNotFoundError,
        ListingRepositoryConfigurationError,
        ListingRepositoryError,
    ) as error:
        raise listing_error(error) from error


@router.patch(
    "/listing-drafts/{draft_id}",
    response_model=ListingDraftResponse,
)
def update_listing_draft(
    draft_id: UUID,
    draft_update: ListingDraftUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ListingDraftResponse:
    try:
        repository = get_listing_repository()
        audit_repository = get_audit_repository()
        existing_draft = repository.get_draft(
            owner_id=user.user_id,
            access_token=user.access_token,
            draft_id=draft_id,
        )

        selected_observation_id = None
        if draft_update.changes_price:
            if draft_update.price_amount is None or draft_update.currency is None:
                raise ValueError("Validated price update is incomplete")
            selected_observation_id = (
                get_pricing_repository().create_manual_observation(
                    owner_id=user.user_id,
                    access_token=user.access_token,
                    card_id=existing_draft.card_id,
                    price_amount=draft_update.price_amount,
                    currency=draft_update.currency,
                )
            )

        updated_draft = repository.update_draft(
            owner_id=user.user_id,
            access_token=user.access_token,
            draft_id=draft_id,
            draft_update=draft_update,
            selected_pricing_observation_id=selected_observation_id,
        )
        audit_repository.create_listing_event(
            owner_id=user.user_id,
            actor_id=user.user_id,
            action="listing_draft.updated",
            draft_id=updated_draft.id,
            old_data=audit_data(existing_draft),
            new_data=audit_data(updated_draft),
        )
        return updated_draft
    except (
        AuditRepositoryConfigurationError,
        AuditRepositoryError,
        ListingDraftNotFoundError,
        ListingRepositoryConfigurationError,
        ListingRepositoryError,
        PricingRepositoryConfigurationError,
        PricingRepositoryError,
    ) as error:
        raise listing_error(error) from error
