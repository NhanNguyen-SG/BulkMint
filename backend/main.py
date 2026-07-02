import base64
import json
from functools import lru_cache
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from app_config import AppSettings
from auth import AuthenticatedUser, get_current_user
from cards_api import router as cards_router
from image_validation import read_validated_image
from listing_api import router as listing_router

load_dotenv()

settings = AppSettings.from_environment()
app = FastAPI(
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.include_router(cards_router)
app.include_router(listing_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI()


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "BulkMint backend is running"}


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    image = await read_validated_image(file)
    base64_image = base64.b64encode(image.content).decode("utf-8")

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
                        "image_url": {
                            "url": f"data:{image.content_type};base64,{base64_image}"
                        },
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
