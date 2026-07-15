"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DraftDisplay } from "./draft-display";
import { DraftEditor } from "./draft-editor";
import { DraftVersionSelector } from "./draft-version-selector";
import { draftKeywords, itemSpecificRows } from "./item-specifics-table";

import {
  createListingDraft,
  fetchListingDrafts,
  updateListingDraft,
} from "@/lib/api/listing-drafts";
import { errorMessage, reportUnexpectedError } from "@/lib/api/client";
import type { DraftForm, ListingDraft } from "@/types/listings";

type ListingDraftPanelProps = {
  cardId: string;
  cardGame: string;
  cardName: string;
  cardImageUrl: string | null;
  cardSet: string;
  cardNumber: string;
  cardRarity: string;
  cardCondition: string;
  onClose: () => void;
};

function formFromDraft(draft: ListingDraft): DraftForm {
  return {
    title: draft.title,
    description: draft.description,
    status: draft.status,
    category_suggestion: draft.category_suggestion ?? "",
    item_specifics_json: JSON.stringify(draft.item_specifics_json, null, 2),
    price_amount: draft.price_amount === null ? "" : String(draft.price_amount),
    currency: draft.currency,
  };
}

function validateDraftForm(
  selectedDraft: ListingDraft,
  form: DraftForm,
): string | null {
  if (!form.title.trim() || !form.description.trim()) {
    return "Title and description are required.";
  }

  let itemSpecifics: unknown;
  try {
    itemSpecifics = JSON.parse(form.item_specifics_json);
  } catch {
    return "Item specifics must be valid JSON.";
  }
  if (
    typeof itemSpecifics !== "object" ||
    itemSpecifics === null ||
    Array.isArray(itemSpecifics)
  ) {
    return "Item specifics must be a JSON object.";
  }

  const numericPrice =
    form.price_amount.trim() === "" ? null : Number(form.price_amount);
  if (numericPrice !== null && (!Number.isFinite(numericPrice) || numericPrice < 0)) {
    return "Price must be a non-negative number.";
  }
  if (form.status === "ready" && numericPrice === null) {
    return "A ready draft requires a price.";
  }
  if (selectedDraft.price_amount !== null && numericPrice === null) {
    return "The current API does not support clearing a persisted price.";
  }
  const normalizedCurrency = form.currency.trim().toUpperCase();
  if (numericPrice !== null && !/^[A-Z]{3}$/.test(normalizedCurrency)) {
    return "Currency must be a three-letter code.";
  }

  return null;
}

export function ListingDraftPanel({
  cardId,
  cardGame,
  cardName,
  cardImageUrl,
  cardSet,
  cardNumber,
  cardRarity,
  cardCondition,
  onClose,
}: ListingDraftPanelProps) {
  const [drafts, setDrafts] = useState<ListingDraft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<ListingDraft | null>(null);
  const [form, setForm] = useState<DraftForm | null>(null);
  const [editing, setEditing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);
  const [imagePreviewOpen, setImagePreviewOpen] = useState(false);
  const generatedCardRef = useRef<string | null>(null);
  const imageTriggerRef = useRef<HTMLButtonElement>(null);

  const closeImagePreview = useCallback(() => {
    setImagePreviewOpen(false);
    window.requestAnimationFrame(() => imageTriggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!imagePreviewOpen) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") closeImagePreview();
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closeImagePreview, imagePreviewOpen]);

  const selectDraft = useCallback((draft: ListingDraft) => {
    setSelectedDraft(draft);
    setForm(formFromDraft(draft));
    setEditing(false);
    setCopySuccess(null);
  }, []);

  const loadDrafts = useCallback(
    async (preferredDraftId?: string) => {
      setLoadingDrafts(true);
      try {
        const loadedDrafts = await fetchListingDrafts(cardId);
        setDrafts(loadedDrafts);
        const preferredDraft =
          loadedDrafts.find((draft) => draft.id === preferredDraftId) ??
          loadedDrafts[0] ??
          null;
        if (preferredDraft) {
          selectDraft(preferredDraft);
        } else {
          setSelectedDraft(null);
          setForm(null);
        }
      } finally {
        setLoadingDrafts(false);
      }
    },
    [cardId, selectDraft],
  );

  const generateDraft = useCallback(async () => {
    if (generating) return;

    setGenerating(true);
    setError(null);
    setSuccess(null);
    setCopySuccess(null);

    try {
      const createdDraft = await createListingDraft(cardId);
      await loadDrafts(createdDraft.id);
      setSuccess(`Draft v${createdDraft.version} created.`);
    } catch (caughtError) {
      reportUnexpectedError("Listing draft generation error:", caughtError);
      setError(errorMessage(caughtError, "Unable to generate listing draft."));
    } finally {
      setGenerating(false);
    }
  }, [cardId, generating, loadDrafts]);

  useEffect(() => {
    if (generatedCardRef.current === cardId) return;
    generatedCardRef.current = cardId;
    // The inventory action explicitly requests generation when this panel opens.
    void generateDraft();
  }, [cardId, generateDraft]);

  function updateForm<FieldName extends keyof DraftForm>(
    field: FieldName,
    value: DraftForm[FieldName],
  ) {
    setForm((current) => (current ? { ...current, [field]: value } : current));
  }

  async function refreshDrafts() {
    setError(null);
    setSuccess(null);
    try {
      await loadDrafts(selectedDraft?.id);
    } catch (caughtError) {
      reportUnexpectedError("Listing draft refresh error:", caughtError);
      setError(errorMessage(caughtError, "Unable to refresh listing drafts."));
    }
  }

  async function saveDraft() {
    if (!selectedDraft || !form || saving) return;

    const validationError = validateDraftForm(selectedDraft, form);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedDraft = await updateListingDraft(selectedDraft, form);
      setDrafts((current) =>
        current.map((draft) =>
          draft.id === updatedDraft.id ? updatedDraft : draft,
        ),
      );
      selectDraft(updatedDraft);
      setSuccess(`Draft saved as v${updatedDraft.version}.`);
    } catch (caughtError) {
      reportUnexpectedError("Listing draft save error:", caughtError);
      setError(errorMessage(caughtError, "Unable to save listing draft."));
    } finally {
      setSaving(false);
    }
  }

  async function copyText(label: string, value: string) {
    setError(null);
    setCopySuccess(null);
    try {
      await navigator.clipboard.writeText(value);
      setCopySuccess(`${label} copied.`);
    } catch (caughtError) {
      console.error("Clipboard error:", caughtError);
      setError("Unable to copy to the clipboard.");
    }
  }

  const newestDraftId =
    drafts.reduce<ListingDraft | null>((newest, draft) => {
      if (!newest) return draft;
      return Date.parse(draft.created_at) > Date.parse(newest.created_at)
        ? draft
        : newest;
    }, null)?.id ?? null;
  const specifics = selectedDraft
    ? itemSpecificRows(selectedDraft.item_specifics_json, {
        Game: cardGame,
        "Card Name": cardName,
        Set: cardSet,
        "Card Number": cardNumber,
        Rarity: cardRarity,
        Condition: cardCondition,
      })
    : [];
  const keywords = selectedDraft
    ? draftKeywords(selectedDraft.item_specifics_json)
    : [];

  return (
    <section className="mt-4 border-t border-zinc-800 pt-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">Listing Drafts</h3>
          <p className="text-xs text-zinc-500">{cardName}</p>
          <p className="text-xs text-zinc-500">Game: {cardGame}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="Close listing drafts"
          className="rounded px-2 py-1 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
        >
          Close
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void generateDraft()}
          disabled={generating || saving}
          title="Generate a new AI listing draft"
          className="rounded-md bg-green-500 px-3 py-1.5 text-sm font-semibold text-black hover:bg-green-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-300 disabled:bg-zinc-700 disabled:text-zinc-300"
        >
          {generating
            ? "Generating…"
            : drafts.length > 0
              ? "Generate Another Draft"
              : "Generate Draft"}
        </button>
        <button
          type="button"
          onClick={() => void refreshDrafts()}
          disabled={loadingDrafts || generating}
          title="Refresh saved draft versions"
          className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-200 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400 disabled:opacity-60"
        >
          {loadingDrafts ? "Loading…" : "Refresh Versions"}
        </button>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {error}
        </p>
      )}
      {success && (
        <p role="status" className="mt-3 text-sm text-green-400">
          {success}
        </p>
      )}
      {copySuccess && (
        <p role="status" className="mt-3 text-sm text-green-400">
          {copySuccess}
        </p>
      )}

      {(generating || (loadingDrafts && drafts.length === 0)) && (
        <div
          role="status"
          className="mt-4 flex items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-950/70 p-3 text-sm text-zinc-300"
        >
          <span
            aria-hidden="true"
            className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-green-400"
          />
          {generating
            ? "Generating and validating your listing draft…"
            : "Loading draft versions…"}
        </div>
      )}

      {!generating && !loadingDrafts && drafts.length === 0 && (
        <div className="mt-4 rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 p-4">
          <p className="text-sm font-medium text-zinc-200">No drafts yet</p>
          <p className="mt-1 text-sm text-zinc-400">
            Generate a draft to review listing details, pricing, and keywords.
          </p>
        </div>
      )}

      <DraftVersionSelector
        drafts={drafts}
        selectedDraftId={selectedDraft?.id ?? null}
        newestDraftId={newestDraftId}
        onSelect={selectDraft}
      />

      {selectedDraft && form && !editing && (
        <DraftDisplay
          draft={selectedDraft}
          newestDraftId={newestDraftId}
          cardName={cardName}
          cardImageUrl={cardImageUrl}
          specifics={specifics}
          keywords={keywords}
          imagePreviewOpen={imagePreviewOpen}
          imageTriggerRef={imageTriggerRef}
          onEdit={() => {
            setEditing(true);
            setError(null);
            setSuccess(null);
          }}
          onCopy={(label, value) => void copyText(label, value)}
          onOpenImagePreview={() => setImagePreviewOpen(true)}
          onCloseImagePreview={closeImagePreview}
        />
      )}

      {selectedDraft && form && editing && (
        <DraftEditor
          selectedDraft={selectedDraft}
          form={form}
          saving={saving}
          onUpdate={updateForm}
          onSave={() => void saveDraft()}
          onCancel={() => {
            setForm(formFromDraft(selectedDraft));
            setEditing(false);
            setError(null);
          }}
        />
      )}
    </section>
  );
}
