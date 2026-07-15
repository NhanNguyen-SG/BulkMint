export type CardDetection = {
  index: number;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
};

export type CardDetectionResponse = {
  image_width: number;
  image_height: number;
  count: number;
  detections: CardDetection[];
  debug_image: string;
};
