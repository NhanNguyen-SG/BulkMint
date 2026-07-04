import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener  # type: ignore[import-untyped]

MAX_IMAGE_BYTES = 25 * 1024 * 1024
NORMALIZED_MAX_DIMENSION = 4096
NORMALIZED_JPEG_QUALITY = 90

register_heif_opener(thumbnails=False)


@dataclass(frozen=True)
class ImageFormat:
    pillow_format: str
    content_type: str
    extension: str


IMAGE_FORMATS_BY_MIME = {
    "image/jpeg": ImageFormat("JPEG", "image/jpeg", "jpg"),
    "image/jpg": ImageFormat("JPEG", "image/jpeg", "jpg"),
    "image/png": ImageFormat("PNG", "image/png", "png"),
    "image/webp": ImageFormat("WEBP", "image/webp", "webp"),
    "image/heic": ImageFormat("HEIF", "image/heic", "heic"),
    "image/heif": ImageFormat("HEIF", "image/heif", "heif"),
    "image/avif": ImageFormat("AVIF", "image/avif", "avif"),
}
IMAGE_FORMATS_BY_EXTENSION = {
    ".jpg": IMAGE_FORMATS_BY_MIME["image/jpeg"],
    ".jpeg": IMAGE_FORMATS_BY_MIME["image/jpeg"],
    ".png": IMAGE_FORMATS_BY_MIME["image/png"],
    ".webp": IMAGE_FORMATS_BY_MIME["image/webp"],
    ".heic": IMAGE_FORMATS_BY_MIME["image/heic"],
    ".heif": IMAGE_FORMATS_BY_MIME["image/heif"],
    ".avif": IMAGE_FORMATS_BY_MIME["image/avif"],
}
GENERIC_CONTENT_TYPES = {"", "application/octet-stream"}


@dataclass(frozen=True)
class ImageObject:
    content: bytes
    content_type: str
    extension: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class ValidatedImage:
    original: ImageObject
    normalized: ImageObject

    @property
    def content(self) -> bytes:
        return self.normalized.content

    @property
    def content_type(self) -> str:
        return self.normalized.content_type

    @property
    def extension(self) -> str:
        return self.normalized.extension

    @property
    def byte_size(self) -> int:
        return self.normalized.byte_size

    @property
    def sha256(self) -> str:
        return self.normalized.sha256


def _upload_format(file: UploadFile) -> ImageFormat:
    content_type = (file.content_type or "").partition(";")[0].strip().lower()
    mime_format = IMAGE_FORMATS_BY_MIME.get(content_type)
    extension_format = IMAGE_FORMATS_BY_EXTENSION.get(Path(file.filename or "").suffix.lower())

    if mime_format is None and content_type not in GENERIC_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, WebP, HEIC, HEIF, or AVIF image",
        )
    if mime_format is None and extension_format is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, WebP, HEIC, HEIF, or AVIF image",
        )
    if (
        mime_format is not None
        and extension_format is not None
        and mime_format.pillow_format != extension_format.pillow_format
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image filename and declared file type do not match",
        )

    resolved_format = extension_format or mime_format
    if resolved_format is None:
        raise AssertionError("Accepted image format resolution failed")
    return resolved_format


def _image_object(
    content: bytes,
    *,
    content_type: str,
    extension: str,
) -> ImageObject:
    return ImageObject(
        content=content,
        content_type=content_type,
        extension=extension,
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _normalized_jpeg(image_bytes: bytes, *, expected_format: str) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as image:
                detected_format = image.format
                image.verify()

            if detected_format != expected_format:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image contents do not match the declared file type",
                )

            with Image.open(BytesIO(image_bytes)) as image:
                image.seek(0)
                image.load()
                normalized = ImageOps.exif_transpose(image)
                normalized.thumbnail(
                    (NORMALIZED_MAX_DIMENSION, NORMALIZED_MAX_DIMENSION),
                    Image.Resampling.LANCZOS,
                )

                if normalized.mode in {"RGBA", "LA"} or "transparency" in normalized.info:
                    rgba = normalized.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    background.alpha_composite(rgba)
                    rgb = background.convert("RGB")
                else:
                    rgb = normalized.convert("RGB")

                output = BytesIO()
                rgb.save(
                    output,
                    format="JPEG",
                    quality=NORMALIZED_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                return output.getvalue()
    except HTTPException:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a readable image",
        ) from error


async def read_validated_image(file: UploadFile) -> ValidatedImage:
    upload_format = _upload_format(file)
    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image must be 25 MB or smaller",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    normalized_bytes = _normalized_jpeg(
        image_bytes,
        expected_format=upload_format.pillow_format,
    )
    return ValidatedImage(
        original=_image_object(
            image_bytes,
            content_type=upload_format.content_type,
            extension=upload_format.extension,
        ),
        normalized=_image_object(
            normalized_bytes,
            content_type="image/jpeg",
            extension="jpg",
        ),
    )
