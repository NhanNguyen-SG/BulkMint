export const SUPPORTED_GAMES = [
  "Pokemon",
  "One Piece",
  "Magic: The Gathering",
  "Yu-Gi-Oh!",
  "Disney Lorcana",
  "Digimon",
  "Dragon Ball Super",
  "Unknown",
] as const;

export type DetectedGame = (typeof SUPPORTED_GAMES)[number];

export const CARD_STATUSES = [
  "draft",
  "active",
  "listed",
  "sold",
  "archived",
] as const;

export type CardStatus = (typeof CARD_STATUSES)[number];

export type CardAnalysisResult = {
  detected_game: DetectedGame;
  card_name: string;
  set: string;
  card_number: string;
  rarity: string;
  condition_guess: string;
  suggested_price: string;
  ebay_title: string;
  ebay_description: string;
};

export type InventoryCard = CardAnalysisResult & {
  id: string;
  created_at: string;
  price_amount: number | string | null;
  currency: string;
  status: CardStatus;
  image_id: string | null;
  image_url: string | null;
};

export type EditCardForm = {
  detected_game: DetectedGame;
  card_name: string;
  set: string;
  card_number: string;
  rarity: string;
  condition_guess: string;
  price_amount: string;
  currency: string;
  status: CardStatus;
};

export type InventoryFilters = {
  q: string;
  status: "" | CardStatus;
  detected_game: "" | DetectedGame;
  set_name: string;
  rarity: string;
};

export const EMPTY_INVENTORY_FILTERS: InventoryFilters = {
  q: "",
  status: "",
  detected_game: "",
  set_name: "",
  rarity: "",
};
