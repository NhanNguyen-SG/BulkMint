import type {
  CardAnalysisResult,
  EditCardForm,
  InventoryCard,
  InventoryFilters,
} from "@/types/cards";

import { authenticatedApiFetch } from "./authenticated-fetch";
import { apiError } from "./client";

export async function fetchCards(
  filters: InventoryFilters,
): Promise<InventoryCard[]> {
  const query = new URLSearchParams({ limit: "50" });
  if (filters.q.trim()) query.set("q", filters.q.trim());
  if (filters.status) query.set("status", filters.status);
  if (filters.detected_game) query.set("detected_game", filters.detected_game);
  if (filters.set_name.trim()) query.set("set_name", filters.set_name.trim());
  if (filters.rarity.trim()) query.set("rarity", filters.rarity.trim());

  const response = await authenticatedApiFetch(`/cards?${query.toString()}`);
  if (!response.ok) {
    throw await apiError(response, "Unable to load inventory");
  }

  return response.json() as Promise<InventoryCard[]>;
}

export async function analyzeCardImage(file: File): Promise<CardAnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await authenticatedApiFetch("/analyze-card", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to analyze card");
  }

  return response.json() as Promise<CardAnalysisResult>;
}

export async function createCard(
  card: CardAnalysisResult,
  image: File | null,
): Promise<InventoryCard> {
  const formData = new FormData();
  formData.append("card", JSON.stringify(card));
  if (image) {
    formData.append("image", image);
  }

  const response = await authenticatedApiFetch("/cards", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to save card");
  }

  return response.json() as Promise<InventoryCard>;
}

export async function updateCard(
  cardId: string,
  editForm: EditCardForm,
): Promise<InventoryCard> {
  const response = await authenticatedApiFetch(`/cards/${cardId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      detected_game: editForm.detected_game,
      card_name: editForm.card_name,
      set: editForm.set,
      card_number: editForm.card_number,
      rarity: editForm.rarity,
      condition_guess: editForm.condition_guess,
      price_amount:
        editForm.price_amount.trim() === ""
          ? null
          : Number(editForm.price_amount),
      currency: editForm.currency,
      status: editForm.status,
    }),
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to update card");
  }

  return response.json() as Promise<InventoryCard>;
}

export async function archiveCardById(cardId: string): Promise<InventoryCard> {
  const response = await authenticatedApiFetch(`/cards/${cardId}/archive`, {
    method: "PATCH",
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to archive card");
  }

  return response.json() as Promise<InventoryCard>;
}

export async function deleteCardById(cardId: string): Promise<void> {
  const response = await authenticatedApiFetch(`/cards/${cardId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to delete card");
  }
}
