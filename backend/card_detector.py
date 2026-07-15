import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from card_detection_models import CardDetection, CardDetectionResponse
from image_validation import ValidatedImage

BOUNDARY_MARGIN_RATIO = 0.01
DEBUG_JPEG_QUALITY = 88


class CardDetectionError(RuntimeError):
    """Raised when an already-validated image cannot be processed for detection."""


@dataclass(frozen=True)
class CardDetectionSettings:
    min_card_area_ratio: float = 0.015
    portrait_aspect_ratio_range: tuple[float, float] = (0.55, 0.85)
    landscape_aspect_ratio_range: tuple[float, float] = (1.15, 1.85)
    max_detection_count: int = 20
    overlap_iou_threshold: float = 0.35


@dataclass(frozen=True)
class DetectionCandidate:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    area: float


class OpenCVCardDetector:
    def __init__(
        self,
        settings: CardDetectionSettings = CardDetectionSettings(),
    ) -> None:
        self.settings = settings

    def detect(self, image: ValidatedImage) -> CardDetectionResponse:
        pil_image = self._decode_image(image.content)
        rgb_image = np.array(pil_image)
        image_height, image_width = rgb_image.shape[:2]

        candidates = self._detect_candidates(rgb_image)
        detections = [
            CardDetection(
                index=index,
                x=candidate.x,
                y=candidate.y,
                width=candidate.width,
                height=candidate.height,
                confidence=candidate.confidence,
            )
            for index, candidate in enumerate(candidates)
        ]

        return CardDetectionResponse(
            image_width=image_width,
            image_height=image_height,
            count=len(detections),
            detections=detections,
            debug_image=render_debug_preview(pil_image, detections),
        )

    @staticmethod
    def _decode_image(content: bytes) -> Image.Image:
        try:
            with Image.open(BytesIO(content)) as image:
                return image.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise CardDetectionError("Validated image could not be decoded") from error

    def _detect_candidates(self, rgb_image: Any) -> list[DetectionCandidate]:
        image_height, image_width = rgb_image.shape[:2]
        image_area = image_width * image_height
        minimum_area = image_area * self.settings.min_card_area_ratio
        margin = int(min(image_width, image_height) * BOUNDARY_MARGIN_RATIO)

        gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        dilated = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        contours, _hierarchy = cv2.findContours(
            dilated,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        candidates: list[DetectionCandidate] = []
        for contour in contours:
            contour_area = float(cv2.contourArea(contour))
            if contour_area < minimum_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue

            polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue

            x, y, width, height = cv2.boundingRect(polygon)
            if width <= 0 or height <= 0:
                continue
            if (
                x < margin
                or y < margin
                or x + width > image_width - margin
                or y + height > image_height - margin
            ):
                continue

            box_area = width * height
            if box_area < minimum_area:
                continue

            aspect_ratio = width / height
            portrait_match = (
                self.settings.portrait_aspect_ratio_range[0]
                <= aspect_ratio
                <= self.settings.portrait_aspect_ratio_range[1]
            )
            landscape_match = (
                self.settings.landscape_aspect_ratio_range[0]
                <= aspect_ratio
                <= self.settings.landscape_aspect_ratio_range[1]
            )
            if not portrait_match and not landscape_match:
                continue

            rectangularity = min(1.0, contour_area / box_area)
            if portrait_match:
                target_aspect = sum(self.settings.portrait_aspect_ratio_range) / 2
                aspect_span = (
                    self.settings.portrait_aspect_ratio_range[1]
                    - self.settings.portrait_aspect_ratio_range[0]
                ) / 2
            else:
                target_aspect = sum(self.settings.landscape_aspect_ratio_range) / 2
                aspect_span = (
                    self.settings.landscape_aspect_ratio_range[1]
                    - self.settings.landscape_aspect_ratio_range[0]
                ) / 2
            aspect_score = max(0.0, 1.0 - abs(aspect_ratio - target_aspect) / aspect_span)
            contour_quality = min(1.0, perimeter / (2 * (width + height)))
            # Heuristic geometry score only; this is not machine-learning confidence.
            confidence = round(
                max(
                    0.0,
                    min(
                        1.0,
                        0.5 * rectangularity
                        + 0.35 * aspect_score
                        + 0.15 * contour_quality,
                    ),
                ),
                2,
            )
            candidates.append(
                DetectionCandidate(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    confidence=confidence,
                    area=contour_area,
                )
            )

        return self._suppress_and_sort(candidates, self.settings)

    @staticmethod
    def _suppress_and_sort(
        candidates: list[DetectionCandidate],
        settings: CardDetectionSettings = CardDetectionSettings(),
    ) -> list[DetectionCandidate]:
        selected: list[DetectionCandidate] = []
        for candidate in sorted(
            candidates,
            key=lambda item: (item.confidence, item.area),
            reverse=True,
        ):
            if all(
                _iou(candidate, existing) <= settings.overlap_iou_threshold
                for existing in selected
            ):
                selected.append(candidate)
            if len(selected) >= settings.max_detection_count:
                break

        return sorted(selected, key=lambda item: (item.y, item.x))


def _iou(first: DetectionCandidate, second: DetectionCandidate) -> float:
    first_x2 = first.x + first.width
    first_y2 = first.y + first.height
    second_x2 = second.x + second.width
    second_y2 = second.y + second.height

    intersection_x1 = max(first.x, second.x)
    intersection_y1 = max(first.y, second.y)
    intersection_x2 = min(first_x2, second_x2)
    intersection_y2 = min(first_y2, second_y2)

    intersection_width = max(0, intersection_x2 - intersection_x1)
    intersection_height = max(0, intersection_y2 - intersection_y1)
    intersection_area = intersection_width * intersection_height
    if intersection_area == 0:
        return 0.0

    first_area = first.width * first.height
    second_area = second.width * second.height
    union_area = first_area + second_area - intersection_area
    return intersection_area / union_area if union_area > 0 else 0.0


def render_debug_preview(
    image: Image.Image,
    detections: list[CardDetection],
) -> str:
    preview = image.copy()
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default()

    for detection in detections:
        x1 = detection.x
        y1 = detection.y
        x2 = detection.x + detection.width
        y2 = detection.y + detection.height
        draw.rectangle((x1, y1, x2, y2), outline=(34, 197, 94), width=6)
        label = str(detection.index)
        text_bbox = draw.textbbox((x1, y1), label, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        draw.rectangle(
            (x1, max(0, y1 - text_height - 10), x1 + text_width + 14, y1),
            fill=(34, 197, 94),
        )
        draw.text(
            (x1 + 6, max(0, y1 - text_height - 8)),
            label,
            fill=(0, 0, 0),
            font=font,
        )

    output = BytesIO()
    preview.save(output, format="JPEG", quality=DEBUG_JPEG_QUALITY, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def get_card_detector() -> OpenCVCardDetector:
    return OpenCVCardDetector()
