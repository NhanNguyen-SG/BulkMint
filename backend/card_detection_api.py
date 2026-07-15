from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from auth import AuthenticatedUser, get_current_user
from card_detection_models import CardDetectionResponse
from card_detector import CardDetectionError, get_card_detector
from image_validation import read_validated_image

router = APIRouter(tags=["card-detection"])


@router.post("/detect-cards", response_model=CardDetectionResponse)
async def detect_cards(
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> CardDetectionResponse:
    image = await read_validated_image(file)
    try:
        return get_card_detector().detect(image)
    except CardDetectionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to process image for card detection",
        ) from error
