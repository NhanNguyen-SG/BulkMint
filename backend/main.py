import base64
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "BulkMint backend is running"}


@app.post("/analyze-card")
async def analyze_card(file: UploadFile = File(...)):
    image_bytes = await file.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
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
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
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
