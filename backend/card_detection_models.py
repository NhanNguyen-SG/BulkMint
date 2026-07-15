from pydantic import BaseModel, ConfigDict, Field


class CardDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class CardDetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    count: int = Field(ge=0)
    detections: list[CardDetection]
    debug_image: str
