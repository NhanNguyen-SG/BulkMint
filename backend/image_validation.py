import hashlib
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_FORMATS = {
    "image/jpeg": ("JPEG", "jpg"),
    "image/png": ("PNG", "png"),
    "image/webp": ("WEBP", "webp"),
}


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    content_type: str
    extension: str
    byte_size: int
    sha256: str


async def read_validated_image(file: UploadFile) -> ValidatedImage:
    content_type = (file.content_type or "").lower()
    expected = IMAGE_FORMATS.get(content_type)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, or WebP image",
        )

    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image must be 10 MB or smaller",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            detected_format = image.format
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a readable image",
        ) from error

    expected_format, extension = expected
    if detected_format != expected_format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image contents do not match the declared file type",
        )

    return ValidatedImage(
        content=image_bytes,
        content_type=content_type,
        extension=extension,
        byte_size=len(image_bytes),
        sha256=hashlib.sha256(image_bytes).hexdigest(),
    )
