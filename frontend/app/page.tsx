"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AnalysisReview } from "./components/analysis-review";
import { AuthStatus } from "./components/auth-status";
import { BulkDetectionPreview } from "./components/bulk-detection-preview";
import { InventoryFiltersForm } from "./components/inventory-filters";
import { InventoryList } from "./components/inventory-list";
import { UploadPanel } from "./components/upload-panel";

import {
  analyzeCardImage,
  archiveCardById,
  createCard,
  deleteCardById,
  fetchCards,
  updateCard,
} from "@/lib/api/cards";
import { errorMessage, reportUnexpectedError } from "@/lib/api/client";
import { AuthenticationRequiredError } from "@/lib/api/authenticated-fetch";
import { BROWSER_PREVIEW_TYPES, validateImageFile } from "@/lib/validation/images";
import type {
  CardAnalysisResult,
  EditCardForm,
  InventoryCard,
  InventoryFilters,
} from "@/types/cards";
import { EMPTY_INVENTORY_FILTERS } from "@/types/cards";

export default function Home() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<CardAnalysisResult | null>(null);
  const [inventory, setInventory] = useState<InventoryCard[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [inventoryLoading, setInventoryLoading] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [inventoryError, setInventoryError] = useState<string | null>(null);
  const [inventoryAuthRequired, setInventoryAuthRequired] = useState(false);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditCardForm | null>(null);
  const [editSavingId, setEditSavingId] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccessId, setEditSuccessId] = useState<string | null>(null);
  const [removingCardId, setRemovingCardId] = useState<string | null>(null);
  const [removalAction, setRemovalAction] = useState<"archive" | "delete" | null>(
    null,
  );
  const [removalError, setRemovalError] = useState<string | null>(null);
  const [removalErrorCardId, setRemovalErrorCardId] = useState<string | null>(null);
  const [filterForm, setFilterForm] = useState<InventoryFilters>(
    EMPTY_INVENTORY_FILTERS,
  );
  const [appliedFilters, setAppliedFilters] = useState<InventoryFilters>(
    EMPTY_INVENTORY_FILTERS,
  );
  const [draftCardId, setDraftCardId] = useState<string | null>(null);
  const savingRef = useRef(false);

  const loadInventory = useCallback(async (filters: InventoryFilters) => {
    setInventoryLoading(true);
    setInventoryError(null);
    setInventoryAuthRequired(false);

    try {
      const cards = await fetchCards(filters);
      setInventory(cards);
    } catch (error) {
      if (error instanceof AuthenticationRequiredError) {
        setInventory([]);
        setInventoryAuthRequired(true);
        return;
      }

      console.error("Fetch inventory error:", error);
      setInventoryError(errorMessage(error, "Unable to load inventory."));
    } finally {
      setInventoryLoading(false);
    }
  }, []);

  function updateFilter<FieldName extends keyof InventoryFilters>(
    field: FieldName,
    value: InventoryFilters[FieldName],
  ) {
    setFilterForm((current) => ({ ...current, [field]: value }));
  }

  function applyInventoryFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedFilters(filterForm);
    void loadInventory(filterForm);
  }

  function clearInventoryFilters() {
    setFilterForm(EMPTY_INVENTORY_FILTERS);
    setAppliedFilters(EMPTY_INVENTORY_FILTERS);
    void loadInventory(EMPTY_INVENTORY_FILTERS);
  }

  useEffect(() => {
    // Inventory is loaded asynchronously; state updates occur after the Supabase request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadInventory(EMPTY_INVENTORY_FILTERS);
  }, [loadInventory]);

  useEffect(() => {
    return () => {
      if (selectedImage) {
        URL.revokeObjectURL(selectedImage);
      }
    };
  }, [selectedImage]);

  function selectImageFile(file: File): boolean {
    setUploadError(null);
    setAnalysisError(null);
    setSaveError(null);
    setResult(null);
    setSaved(false);

    const validationError = validateImageFile(file);
    if (validationError) {
      setSelectedFile(null);
      setSelectedImage(null);
      setUploadError(validationError);
      return false;
    }

    const contentType = file.type.trim().toLowerCase();
    setSelectedFile(file);
    setSelectedImage(
      BROWSER_PREVIEW_TYPES.has(contentType) ? URL.createObjectURL(file) : null,
    );
    return true;
  }

  function handleImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!selectImageFile(file)) {
      event.currentTarget.value = "";
    }
  }

  function handleImageDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      selectImageFile(file);
    }
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

    try {
      const data = await analyzeCardImage(selectedFile);
      setResult(data);
    } catch (error) {
      reportUnexpectedError("Card analysis error:", error);
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
      const savedCard = await createCard(result, selectedFile);
      setInventory((previous) => {
        if (previous.some((card) => card.id === savedCard.id)) {
          return previous;
        }
        return [savedCard, ...previous];
      });
      setSaved(true);
    } catch (error) {
      reportUnexpectedError("Inventory save error:", error);
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
    setRemovalError(null);
    setRemovalErrorCardId(null);
    setEditForm({
      detected_game: card.detected_game,
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
      const updatedCard = await updateCard(cardId, editForm);
      setInventory((current) =>
        current.map((card) => (card.id === updatedCard.id ? updatedCard : card)),
      );
      setEditSuccessId(updatedCard.id);
      setEditingCardId(null);
      setEditForm(null);
    } catch (error) {
      reportUnexpectedError("Inventory update error:", error);
      setEditError(errorMessage(error, "Unable to update card."));
    } finally {
      setEditSavingId(null);
    }
  }

  async function archiveCard(cardId: string) {
    if (
      removingCardId ||
      !window.confirm("Archive this card? It will be hidden from the inventory list.")
    ) {
      return;
    }

    setRemovingCardId(cardId);
    setRemovalAction("archive");
    setRemovalError(null);
    setRemovalErrorCardId(null);
    setEditingCardId(null);
    setEditForm(null);

    try {
      const archivedCard = await archiveCardById(cardId);
      if (draftCardId === cardId) setDraftCardId(null);
      setInventory((current) => {
        if (appliedFilters.status === "archived") {
          return current.map((card) =>
            card.id === archivedCard.id ? archivedCard : card,
          );
        }
        return current.filter((card) => card.id !== archivedCard.id);
      });
    } catch (error) {
      reportUnexpectedError("Inventory archive error:", error);
      setRemovalError(errorMessage(error, "Unable to archive card."));
      setRemovalErrorCardId(cardId);
    } finally {
      setRemovingCardId(null);
      setRemovalAction(null);
    }
  }

  async function deleteCard(cardId: string) {
    if (
      removingCardId ||
      !window.confirm(
        "Delete this card permanently? This also removes the stored image.",
      )
    ) {
      return;
    }

    setRemovingCardId(cardId);
    setRemovalAction("delete");
    setRemovalError(null);
    setRemovalErrorCardId(null);
    setEditingCardId(null);
    setEditForm(null);

    try {
      await deleteCardById(cardId);
      setInventory((current) => current.filter((card) => card.id !== cardId));
      if (draftCardId === cardId) setDraftCardId(null);
    } catch (error) {
      reportUnexpectedError("Inventory delete error:", error);
      setRemovalError(errorMessage(error, "Unable to delete card."));
      setRemovalErrorCardId(cardId);
    } finally {
      setRemovingCardId(null);
      setRemovalAction(null);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-5xl bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-2xl md:p-8">
        <div className="mb-6 flex justify-end">
          <AuthStatus />
        </div>

        <h1 className="text-4xl font-bold mb-2">BulkMint</h1>

        <p className="text-zinc-400 mb-8">AI-powered TCG listing assistant</p>

        <p className="mb-4 text-sm text-zinc-400">
          Supports Pokémon, One Piece, MTG, Yu-Gi-Oh!, Lorcana, Digimon,
          Dragon Ball, and more.
        </p>

        <UploadPanel
          selectedFile={selectedFile}
          selectedImage={selectedImage}
          uploadError={uploadError}
          analyzing={analyzing}
          saving={saving}
          onImageUpload={handleImageUpload}
          onImageDrop={handleImageDrop}
          onAnalyze={analyzeCard}
        />

        {analysisError && (
          <p role="alert" className="mt-3 text-sm text-red-400">
            {analysisError}
          </p>
        )}

        {result && (
          <AnalysisReview
            result={result}
            saving={saving}
            saved={saved}
            saveError={saveError}
            onSave={saveCard}
          />
        )}

        <BulkDetectionPreview />

        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-4">Inventory History</h2>

          <InventoryFiltersForm
            filters={filterForm}
            inventoryLoading={inventoryLoading}
            onApply={applyInventoryFilters}
            onClear={clearInventoryFilters}
            onUpdate={updateFilter}
          />

          <InventoryList
            inventory={inventory}
            inventoryLoading={inventoryLoading}
            inventoryError={inventoryError}
            inventoryAuthRequired={inventoryAuthRequired}
            appliedFilters={appliedFilters}
            draftCardId={draftCardId}
            editingCardId={editingCardId}
            editForm={editForm}
            editSavingId={editSavingId}
            editError={editError}
            editSuccessId={editSuccessId}
            removingCardId={removingCardId}
            removalAction={removalAction}
            removalError={removalError}
            removalErrorCardId={removalErrorCardId}
            onStartEditing={startEditing}
            onUpdateEditField={updateEditField}
            onSaveEdit={saveEdit}
            onCancelEditing={cancelEditing}
            onOpenDrafts={setDraftCardId}
            onCloseDrafts={() => setDraftCardId(null)}
            onArchive={archiveCard}
            onDelete={deleteCard}
          />
        </div>
      </div>
    </main>
  );
}
