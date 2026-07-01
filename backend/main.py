import base64
import json
from functools import lru_cache
from io import BytesIO
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from PIL import Image, UnidentifiedImageError

from auth import AuthenticatedUser, get_current_user
from cards_api import router as cards_router

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": {"JPEG"},
    "image/png": {"PNG"},
    "image/webp": {"WEBP"},
}

load_dotenv()

app = FastAPI()
app.include_router(cards_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI()


async def read_validated_image(file: UploadFile) -> tuple[bytes, str]:
    content_type = (file.content_type or "").lower()
    expected_formats = ALLOWED_IMAGE_TYPES.get(content_type)
    if expected_formats is None:
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

    if detected_format not in expected_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image contents do not match the declared file type",
        )

    return image_bytes, content_type


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "BulkMint backend is running"}


@app.get("/me")
def me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> dict[str, str]:
    return {"user_id": str(user.user_id)}


@app.post("/analyze-card")
async def analyze_card(
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> dict[str, Any]:
    image_bytes, content_type = await read_validated_image(file)
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = get_openai_client().chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
Analyze this One Piece trading card for a seller.

Return ONLY valid JSON in this exact format:

{

  "card_name": "",

  "set": "",

  "card_number": "",

  "rarity": "",

  "condition_guess": "",

  "suggested_price": "",

  "ebay_title": "",

  "ebay_description": ""

}

Rules:

- Use the visible card text and card number if possible.

- If unsure, use "Unknown".

- Keep ebay_title under 80 characters.

- Make ebay_description clean and seller-friendly.

- Do not include markdown.

- Do not include explanations.

Only return JSON.
""",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{base64_image}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI returned no response content")

    parsed = json.loads(content)

    return parsed
