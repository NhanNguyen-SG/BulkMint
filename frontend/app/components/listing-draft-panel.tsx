"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  authenticatedApiFetch,
  AuthenticationRequiredError,
} from "@/lib/api/authenticated-fetch";

type ListingDraftStatus = "draft" | "ready" | "archived";

type ListingDraft = {
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

type DraftForm = {
  title: string;
  description: string;
  status: ListingDraftStatus;
  category_suggestion: string;
  item_specifics_json: string;
  price_amount: string;
  currency: string;
};

type ListingDraftPanelProps = {
  cardId: string;
  cardName: string;
  onClose: () => void;
};

const DRAFT_STATUSES: ListingDraftStatus[] = ["draft", "ready", "archived"];

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
    // Use the HTTP fallback when the response is not JSON.
  }
  return new Error(`${fallback} (HTTP ${response.status})`);
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof AuthenticationRequiredError) {
    return "Log in before continuing.";
  }
  return error instanceof Error ? error.message : fallback;
}

function reportUnexpectedError(message: string, error: unknown) {
  if (!(error instanceof AuthenticationRequiredError)) {
    console.error(message, error);
  }
}

function formFromDraft(draft: ListingDraft): DraftForm {
  return {
    title: draft.title,
    description: draft.description,
    status: draft.status,
    category_suggestion: draft.category_suggestion ?? "",
    item_specifics_json: JSON.stringify(draft.item_specifics_json, null, 2),
    price_amount:
      draft.price_amount === null ? "" : String(draft.price_amount),
    currency: draft.currency,
  };
}

export function ListingDraftPanel({
  cardId,
  cardName,
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
  const generatedCardRef = useRef<string | null>(null);

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
        const response = await authenticatedApiFetch(
          `/cards/${cardId}/listing-drafts`,
        );
        if (!response.ok) {
          throw await apiError(response, "Unable to load listing drafts");
        }

        const loadedDrafts: ListingDraft[] = await response.json();
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
      const response = await authenticatedApiFetch(
        `/cards/${cardId}/listing-drafts`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      if (!response.ok) {
        throw await apiError(response, "Unable to generate listing draft");
      }

      const createdDraft: ListingDraft = await response.json();
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

    if (!form.title.trim() || !form.description.trim()) {
      setError("Title and description are required.");
      return;
    }

    let itemSpecifics: unknown;
    try {
      itemSpecifics = JSON.parse(form.item_specifics_json);
    } catch {
      setError("Item specifics must be valid JSON.");
      return;
    }
    if (
      typeof itemSpecifics !== "object" ||
      itemSpecifics === null ||
      Array.isArray(itemSpecifics)
    ) {
      setError("Item specifics must be a JSON object.");
      return;
    }

    const numericPrice =
      form.price_amount.trim() === "" ? null : Number(form.price_amount);
    if (numericPrice !== null && (!Number.isFinite(numericPrice) || numericPrice < 0)) {
      setError("Price must be a non-negative number.");
      return;
    }
    if (form.status === "ready" && numericPrice === null) {
      setError("A ready draft requires a price.");
      return;
    }
    if (selectedDraft.price_amount !== null && numericPrice === null) {
      setError("The current API does not support clearing a persisted price.");
      return;
    }
    const normalizedCurrency = form.currency.trim().toUpperCase();
    if (numericPrice !== null && !/^[A-Z]{3}$/.test(normalizedCurrency)) {
      setError("Currency must be a three-letter code.");
      return;
    }

    const payload: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description.trim(),
      status: form.status,
      category_suggestion: form.category_suggestion.trim() || null,
      item_specifics_json: itemSpecifics,
    };
    const existingNumericPrice =
      selectedDraft.price_amount === null
        ? null
        : Number(selectedDraft.price_amount);
    const priceChanged =
      numericPrice !== existingNumericPrice ||
      normalizedCurrency !== selectedDraft.currency;
    if (numericPrice !== null && priceChanged) {
      payload.price_amount = numericPrice;
      payload.currency = normalizedCurrency;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await authenticatedApiFetch(
        `/listing-drafts/${selectedDraft.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) {
        throw await apiError(response, "Unable to save listing draft");
      }

      const updatedDraft: ListingDraft = await response.json();
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

  return (
    <section className="mt-4 border-t border-zinc-800 pt-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">Listing Drafts</h3>
          <p className="text-xs text-zinc-500">{cardName}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-zinc-400 hover:text-white"
        >
          Close
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void generateDraft()}
          disabled={generating || saving}
          className="rounded-md bg-green-500 px-3 py-1.5 text-sm font-semibold text-black hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
        >
          {generating ? "Generating…" : "Generate Another Draft"}
        </button>
        <button
          type="button"
          onClick={() => void refreshDrafts()}
          disabled={loadingDrafts || generating}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:border-zinc-500 disabled:opacity-60"
        >
          {loadingDrafts ? "Loading…" : "Refresh Versions"}
        </button>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {error}
        </p>
      )}
      {success && <p className="mt-3 text-sm text-green-400">{success}</p>}
      {copySuccess && (
        <p className="mt-3 text-sm text-green-400">{copySuccess}</p>
      )}

      {loadingDrafts && drafts.length === 0 && (
        <p className="mt-3 text-sm text-zinc-500">Loading draft versions…</p>
      )}

      {drafts.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
            Draft versions
          </p>
          <div className="flex flex-wrap gap-2">
            {drafts.map((draft, index) => (
              <button
                key={draft.id}
                type="button"
                onClick={() => selectDraft(draft)}
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  selectedDraft?.id === draft.id
                    ? "border-green-500 text-green-300"
                    : "border-zinc-700 text-zinc-300 hover:border-zinc-500"
                }`}
              >
                Draft {drafts.length - index} · v{draft.version}
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedDraft && form && !editing && (
        <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {selectedDraft.status} · Version {selectedDraft.version}
            </p>
            <button
              type="button"
              onClick={() => {
                setEditing(true);
                setError(null);
                setSuccess(null);
              }}
              className="rounded-md border border-zinc-700 px-3 py-1 text-sm text-zinc-200 hover:border-green-500"
            >
              Edit Draft
            </button>
          </div>

          <p className="mt-3 font-semibold">{selectedDraft.title}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-300">
            {selectedDraft.description}
          </p>
          <dl className="mt-4 grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-zinc-500">Price</dt>
              <dd>
                {selectedDraft.price_amount === null
                  ? "Not set"
                  : selectedDraft.price_amount}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Currency</dt>
              <dd>{selectedDraft.currency}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-zinc-500">Category suggestion</dt>
              <dd>{selectedDraft.category_suggestion ?? "Not set"}</dd>
            </div>
          </dl>
          <div className="mt-4">
            <p className="text-sm text-zinc-500">Item specifics</p>
            <pre className="mt-1 overflow-x-auto rounded-md bg-zinc-950 p-3 text-xs text-zinc-300">
              {JSON.stringify(selectedDraft.item_specifics_json, null, 2)}
            </pre>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void copyText("Title", selectedDraft.title)}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:border-zinc-500"
            >
              Copy Title
            </button>
            <button
              type="button"
              onClick={() =>
                void copyText("Description", selectedDraft.description)
              }
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:border-zinc-500"
            >
              Copy Description
            </button>
            <button
              type="button"
              onClick={() =>
                void copyText(
                  "JSON",
                  JSON.stringify(selectedDraft, null, 2),
                )
              }
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:border-zinc-500"
            >
              Copy JSON
            </button>
          </div>
        </div>
      )}

      {selectedDraft && form && editing && (
        <div className="mt-4 space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <label className="block text-sm">
            <span className="mb-1 block text-zinc-400">Title</span>
            <input
              value={form.title}
              onChange={(event) => updateForm("title", event.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-zinc-400">Description</span>
            <textarea
              rows={5}
              value={form.description}
              onChange={(event) => updateForm("description", event.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
            />
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-zinc-400">Price</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.price_amount}
                onChange={(event) =>
                  updateForm("price_amount", event.target.value)
                }
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-zinc-400">Currency</span>
              <input
                maxLength={3}
                value={form.currency}
                onChange={(event) =>
                  updateForm("currency", event.target.value.toUpperCase())
                }
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-zinc-400">Status</span>
              <select
                value={form.status}
                onChange={(event) =>
                  updateForm(
                    "status",
                    event.target.value as ListingDraftStatus,
                  )
                }
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
              >
                {DRAFT_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-zinc-400">
                Category suggestion
              </span>
              <input
                value={form.category_suggestion}
                onChange={(event) =>
                  updateForm("category_suggestion", event.target.value)
                }
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-zinc-400">
              Item specifics JSON
            </span>
            <textarea
              rows={7}
              spellCheck={false}
              value={form.item_specifics_json}
              onChange={(event) =>
                updateForm("item_specifics_json", event.target.value)
              }
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs"
            />
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void saveDraft()}
              disabled={saving}
              className="rounded-md bg-green-500 px-4 py-2 text-sm font-semibold text-black hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
            >
              {saving ? "Saving…" : "Save Draft"}
            </button>
            <button
              type="button"
              onClick={() => {
                setForm(formFromDraft(selectedDraft));
                setEditing(false);
                setError(null);
              }}
              disabled={saving}
              className="rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:border-zinc-500 disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
