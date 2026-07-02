"use client";

import { useEffect, useRef, useState } from "react";
import {
  authenticatedApiFetch,
  AuthenticationRequiredError,
} from "@/lib/api/authenticated-fetch";
import { AuthStatus } from "./components/auth-status";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type AnalysisResult = {
  card_name: string;
  set: string;
  card_number: string;
  rarity: string;
  condition_guess: string;
  suggested_price: string;
  ebay_title: string;
  ebay_description: string;
};

type InventoryCard = AnalysisResult & {
  id: string;
  created_at: string;
  price_amount: number | string | null;
  currency: string;
  status: "draft" | "active" | "listed" | "sold" | "archived";
  image_id: string | null;
  image_url: string | null;
};

type EditCardForm = {
  card_name: string;
  set: string;
  card_number: string;
  rarity: string;
  condition_guess: string;
  price_amount: string;
  currency: string;
  status: InventoryCard["status"];
};

const CARD_STATUSES: InventoryCard["status"][] = [
  "draft",
  "active",
  "listed",
  "sold",
  "archived",
];

async function apiError(response: Response, fallback: string): Promise<Error> {
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return new Error(body.detail);
    }
  } catch {
    // Use the status-based fallback when the response is not JSON.
  }

  return new Error(`${fallback} (HTTP ${response.status})`);
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof AuthenticationRequiredError) {
    return "Log in before continuing.";
  }
  return error instanceof Error ? error.message : fallback;
}

export default function Home() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [inventory, setInventory] = useState<InventoryCard[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [inventoryError, setInventoryError] = useState<string | null>(null);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditCardForm | null>(null);
  const [editSavingId, setEditSavingId] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccessId, setEditSuccessId] = useState<string | null>(null);
  const savingRef = useRef(false);

  async function fetchInventory() {
    setInventoryLoading(true);
    setInventoryError(null);

    try {
      const response = await authenticatedApiFetch("/cards");
      if (!response.ok) {
        throw await apiError(response, "Unable to load inventory");
      }

      const cards: InventoryCard[] = await response.json();
      setInventory(cards);
    } catch (error) {
      console.error("Fetch inventory error:", error);
      setInventoryError(errorMessage(error, "Unable to load inventory."));
    } finally {
      setInventoryLoading(false);
    }
  }

  useEffect(() => {
    // Inventory is loaded asynchronously; state updates occur after the Supabase request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchInventory();
  }, []);

  useEffect(() => {
    return () => {
      if (selectedImage) {
        URL.revokeObjectURL(selectedImage);
      }
    };
  }, [selectedImage]);

  function handleImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setAnalysisError(null);
    setSaveError(null);
    setResult(null);
    setSaved(false);

    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setSelectedFile(null);
      setSelectedImage(null);
      setUploadError("Choose a JPEG, PNG, or WebP image.");
      event.currentTarget.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setSelectedFile(null);
      setSelectedImage(null);
      setUploadError("Image must be 10 MB or smaller.");
      event.currentTarget.value = "";
      return;
    }

    setSelectedFile(file);
    setSelectedImage(URL.createObjectURL(file));
  }

  async function analyzeCard() {
    if (!selectedFile) {
      setAnalysisError("Choose a card image before analyzing.");
      return;
    }

    setAnalyzing(true);
    setAnalysisError(null);
    setSaveError(null);
    setResult(null);
    setSaved(false);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await authenticatedApiFetch("/analyze-card", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw await apiError(response, "Unable to analyze card");
      }

      const data: AnalysisResult = await response.json();
      setResult(data);
    } catch (error) {
      console.error("Card analysis error:", error);
      setAnalysisError(errorMessage(error, "Unable to analyze card."));
    } finally {
      setAnalyzing(false);
    }
  }

  async function saveCard() {
    if (!result || saved || savingRef.current) {
      return;
    }

    savingRef.current = true;
    setSaving(true);
    setSaveError(null);

    try {
      const formData = new FormData();
      formData.append("card", JSON.stringify(result));
      if (selectedFile) {
        formData.append("image", selectedFile);
      }

      const response = await authenticatedApiFetch("/cards", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw await apiError(response, "Unable to save card");
      }

      const savedCard: InventoryCard = await response.json();
      setInventory((previous) => {
        if (previous.some((card) => card.id === savedCard.id)) {
          return previous;
        }
        return [savedCard, ...previous];
      });
      setSaved(true);
    } catch (error) {
      console.error("Inventory save error:", error);
      setSaveError(errorMessage(error, "Unable to save card."));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  function startEditing(card: InventoryCard) {
    setEditingCardId(card.id);
    setEditError(null);
    setEditSuccessId(null);
    setEditForm({
      card_name: card.card_name,
      set: card.set,
      card_number: card.card_number,
      rarity: card.rarity,
      condition_guess: card.condition_guess,
      price_amount: String(card.price_amount ?? ""),
      currency: card.currency,
      status: card.status,
    });
  }

  function cancelEditing() {
    setEditingCardId(null);
    setEditForm(null);
    setEditError(null);
  }

  function updateEditField<FieldName extends keyof EditCardForm>(
    field: FieldName,
    value: EditCardForm[FieldName],
  ) {
    setEditForm((current) => (current ? { ...current, [field]: value } : current));
  }

  async function saveEdit(cardId: string) {
    if (!editForm || editSavingId) {
      return;
    }

    if (
      !editForm.card_name.trim() ||
      !editForm.set.trim() ||
      !editForm.card_number.trim() ||
      !editForm.rarity.trim() ||
      !editForm.condition_guess.trim()
    ) {
      setEditError("Complete all editable fields before saving.");
      return;
    }

    if (
      editForm.price_amount.trim() !== "" &&
      Number.isNaN(Number(editForm.price_amount))
    ) {
      setEditError("Price must be blank or a valid number.");
      return;
    }

    setEditSavingId(cardId);
    setEditError(null);
    setEditSuccessId(null);

    try {
      const response = await authenticatedApiFetch(`/cards/${cardId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
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

      const updatedCard: InventoryCard = await response.json();
      setInventory((current) =>
        current.map((card) => (card.id === updatedCard.id ? updatedCard : card)),
      );
      setEditSuccessId(updatedCard.id);
      setEditingCardId(null);
      setEditForm(null);
    } catch (error) {
      console.error("Inventory update error:", error);
      setEditError(errorMessage(error, "Unable to update card."));
    } finally {
      setEditSavingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
        <div className="mb-6 flex justify-end">
          <AuthStatus />
        </div>

        <h1 className="text-4xl font-bold mb-2">BulkMint</h1>

        <p className="text-zinc-400 mb-8">
          AI-powered TCG listing assistant
        </p>

        <label
          htmlFor="card-upload"
          className="block border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center hover:border-green-500 transition cursor-pointer"
        >
          <input
            id="card-upload"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleImageUpload}
            className="hidden"
          />

          {selectedImage ? (
            // Local object URLs are generated from the selected file before upload.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={selectedImage}
              alt="Selected card"
              className="mx-auto max-h-80 rounded-xl border border-zinc-700"
            />
          ) : (
            <>
              <p className="text-lg font-medium">Upload Card Image</p>
              <p className="text-sm text-zinc-500 mt-2">
                JPEG, PNG, or WebP · 10 MB maximum
              </p>
            </>
          )}
        </label>

        {uploadError && (
          <p role="alert" className="mt-3 text-sm text-red-400">
            {uploadError}
          </p>
        )}

        <button
          onClick={analyzeCard}
          disabled={!selectedFile || analyzing || saving}
          className="w-full mt-6 bg-green-500 hover:bg-green-400 disabled:bg-zinc-600 disabled:text-zinc-300 text-black font-semibold py-3 rounded-xl transition"
        >
          {analyzing ? "Analyzing…" : "Analyze Card"}
        </button>

        {analysisError && (
          <p role="alert" className="mt-3 text-sm text-red-400">
            {analysisError}
          </p>
        )}

        {result && (
          <div className="mt-6 bg-zinc-950 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-xl font-semibold mb-1">Review Analysis</h2>
            <p className="mb-3 text-sm text-zinc-500">
              Confirm these details before saving.
            </p>
            <p><span className="text-zinc-400">Card:</span> {result.card_name}</p>
            <p><span className="text-zinc-400">Set:</span> {result.set}</p>
            <p><span className="text-zinc-400">Rarity:</span> {result.rarity}</p>
            <p><span className="text-zinc-400">Suggested Price:</span> {result.suggested_price}</p>
            <p><span className="text-zinc-400">Card Number:</span> {result.card_number}</p>
            <p><span className="text-zinc-400">Condition Guess:</span> {result.condition_guess}</p>

            <div className="mt-5 border-t border-zinc-800 pt-4">
              <h3 className="font-semibold mb-2">eBay Draft</h3>
              <p><span className="text-zinc-400">Title:</span> {result.ebay_title}</p>
              <p className="mt-2"><span className="text-zinc-400">Description:</span> {result.ebay_description}</p>
            </div>

            <button
              type="button"
              onClick={saveCard}
              disabled={saving || saved}
              className="mt-5 w-full rounded-lg bg-green-500 py-2.5 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
            >
              {saving ? "Saving…" : saved ? "Saved" : "Save to Inventory"}
            </button>

            {saveError && (
              <p role="alert" className="mt-3 text-sm text-red-400">
                {saveError}
              </p>
            )}
            {saved && (
              <p className="mt-3 text-sm text-green-400">
                Card saved to inventory.
              </p>
            )}
          </div>
        )}

        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-4">Inventory History</h2>

          {inventoryLoading && (
            <p className="text-sm text-zinc-500">Loading inventory…</p>
          )}
          {inventoryError && (
            <p role="alert" className="text-sm text-red-400">
              {inventoryError}
            </p>
          )}
          {!inventoryLoading && !inventoryError && inventory.length === 0 && (
            <p className="text-sm text-zinc-500">No saved cards yet.</p>
          )}

          {inventory.length > 0 && (
            <div className="space-y-4">
              {inventory.map((card) => (
                <div
                  key={card.id}
                  className="bg-zinc-950 border border-zinc-800 rounded-xl p-4"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex items-start gap-3">
                      {card.image_url && (
                        // Signed URLs are short-lived and generated at runtime.
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={card.image_url}
                          alt={`${card.card_name} card`}
                          className="h-20 w-16 rounded-md border border-zinc-700 object-cover"
                        />
                      )}
                      <div>
                        <p className="font-semibold text-lg">{card.card_name}</p>
                        <p className="text-zinc-400">{card.set} • {card.rarity}</p>
                        <p className="text-green-400 mt-2">
                          {card.suggested_price}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-wide text-zinc-500">
                          {card.status}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-zinc-500">#{card.card_number}</div>
                      <button
                        type="button"
                        onClick={() => startEditing(card)}
                        disabled={editSavingId === card.id}
                        className="mt-3 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-200 transition hover:border-green-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Edit
                      </button>
                    </div>
                  </div>

                  {editingCardId === card.id && editForm && (
                    <div className="mt-4 border-t border-zinc-800 pt-4">
                      <p className="mb-3 text-sm text-zinc-400">
                        Update the saved inventory details.
                      </p>

                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Card Name</span>
                          <input
                            value={editForm.card_name}
                            onChange={(event) =>
                              updateEditField("card_name", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Set</span>
                          <input
                            value={editForm.set}
                            onChange={(event) =>
                              updateEditField("set", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Card Number</span>
                          <input
                            value={editForm.card_number}
                            onChange={(event) =>
                              updateEditField("card_number", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Rarity</span>
                          <input
                            value={editForm.rarity}
                            onChange={(event) =>
                              updateEditField("rarity", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Condition</span>
                          <input
                            value={editForm.condition_guess}
                            onChange={(event) =>
                              updateEditField("condition_guess", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Price</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={editForm.price_amount}
                            onChange={(event) =>
                              updateEditField("price_amount", event.target.value)
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Currency</span>
                          <input
                            value={editForm.currency}
                            maxLength={3}
                            onChange={(event) =>
                              updateEditField("currency", event.target.value.toUpperCase())
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          />
                        </label>
                        <label className="text-sm">
                          <span className="mb-1 block text-zinc-400">Status</span>
                          <select
                            value={editForm.status}
                            onChange={(event) =>
                              updateEditField(
                                "status",
                                event.target.value as InventoryCard["status"],
                              )
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
                          >
                            {CARD_STATUSES.map((status) => (
                              <option key={status} value={status}>
                                {status}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="mt-4 flex gap-3">
                        <button
                          type="button"
                          onClick={() => saveEdit(card.id)}
                          disabled={editSavingId === card.id}
                          className="rounded-lg bg-green-500 px-4 py-2 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
                        >
                          {editSavingId === card.id ? "Saving…" : "Save Changes"}
                        </button>
                        <button
                          type="button"
                          onClick={cancelEditing}
                          disabled={editSavingId === card.id}
                          className="rounded-lg border border-zinc-700 px-4 py-2 text-zinc-200 transition hover:border-zinc-500 hover:text-white disabled:opacity-60"
                        >
                          Cancel
                        </button>
                      </div>

                      {editError && (
                        <p role="alert" className="mt-3 text-sm text-red-400">
                          {editError}
                        </p>
                      )}
                    </div>
                  )}

                  {editSuccessId === card.id && editingCardId !== card.id && (
                    <p className="mt-3 text-sm text-green-400">
                      Inventory card updated.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
