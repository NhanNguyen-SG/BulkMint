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
  image_id: string | null;
  image_url: string | null;
};

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
                      </div>
                    </div>

                    <div className="text-right text-sm text-zinc-500">
                      #{card.card_number}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
