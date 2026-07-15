export const DRAFT_STATUSES = ["draft", "ready", "archived"] as const;

export type ListingDraftStatus = (typeof DRAFT_STATUSES)[number];

export type ListingDraft = {
  id: string;
  card_id: string;
  marketplace_target: string;
  version: number;
  status: ListingDraftStatus;
  title: string;
  description: string;
  item_specifics_json: Record<string, unknown>;
  category_suggestion: string | null;
  price_amount: number | string | null;
  currency: string;
  quantity: number;
  prompt_version: string | null;
  ai_model: string | null;
  created_at: string;
  updated_at: string;
};

export type DraftForm = {
  title: string;
  description: string;
  status: ListingDraftStatus;
  category_suggestion: string;
  item_specifics_json: string;
  price_amount: string;
  currency: string;
};
