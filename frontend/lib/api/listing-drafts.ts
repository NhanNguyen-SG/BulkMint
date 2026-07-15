import type { DraftForm, ListingDraft } from "@/types/listings";

import { authenticatedApiFetch } from "./authenticated-fetch";
import { apiError } from "./client";

export async function createListingDraft(cardId: string): Promise<ListingDraft> {
  const response = await authenticatedApiFetch(`/cards/${cardId}/listing-drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to generate listing draft");
  }

  return response.json() as Promise<ListingDraft>;
}

export async function fetchListingDrafts(
  cardId: string,
): Promise<ListingDraft[]> {
  const response = await authenticatedApiFetch(`/cards/${cardId}/listing-drafts`);
  if (!response.ok) {
    throw await apiError(response, "Unable to load listing drafts");
  }

  return response.json() as Promise<ListingDraft[]>;
}

export async function updateListingDraft(
  draft: ListingDraft,
  form: DraftForm,
): Promise<ListingDraft> {
  const itemSpecifics = JSON.parse(form.item_specifics_json) as unknown;
  const normalizedCurrency = form.currency.trim().toUpperCase();
  const numericPrice =
    form.price_amount.trim() === "" ? null : Number(form.price_amount);
  const existingNumericPrice =
    draft.price_amount === null ? null : Number(draft.price_amount);
  const priceChanged =
    numericPrice !== existingNumericPrice || normalizedCurrency !== draft.currency;

  const payload: Record<string, unknown> = {
    title: form.title.trim(),
    description: form.description.trim(),
    status: form.status,
    category_suggestion: form.category_suggestion.trim() || null,
    item_specifics_json: itemSpecifics,
  };

  if (numericPrice !== null && priceChanged) {
    payload.price_amount = numericPrice;
    payload.currency = normalizedCurrency;
  }

  const response = await authenticatedApiFetch(`/listing-drafts/${draft.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await apiError(response, "Unable to save listing draft");
  }

  return response.json() as Promise<ListingDraft>;
}
