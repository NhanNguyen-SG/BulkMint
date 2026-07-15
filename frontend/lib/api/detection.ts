import type { CardDetectionResponse } from "@/types/detection";

import { authenticatedApiFetch } from "./authenticated-fetch";
import { apiError } from "./client";

export async function detectCardsInImage(
  file: File,
): Promise<CardDetectionResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await authenticatedApiFetch("/detect-cards", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to detect cards");
  }

  return response.json() as Promise<CardDetectionResponse>;
}
