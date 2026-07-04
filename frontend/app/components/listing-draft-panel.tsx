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
  cardImageUrl: string | null;
  cardSet: string;
  cardNumber: string;
  cardRarity: string;
  cardCondition: string;
  onClose: () => void;
};

type SpecificRow = {
  label: string;
  value: string;
};

const DRAFT_STATUSES: ListingDraftStatus[] = ["draft", "ready", "archived"];
const COMMON_SPECIFICS = [
  { label: "Card Name", aliases: ["cardname", "name"] },
  { label: "Set", aliases: ["set", "setname"] },
  { label: "Card Number", aliases: ["cardnumber", "number"] },
  { label: "Rarity", aliases: ["rarity"] },
  {
    label: "Condition",
    aliases: ["condition", "conditionsummary", "conditionguess"],
  },
  { label: "Language", aliases: ["language"] },
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function displayValue(value: unknown): string | null {
  if (typeof value === "string") {
    return value.trim() || null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (
    Array.isArray(value) &&
    value.every((item) => typeof item === "string")
  ) {
    return value.join(", ");
  }
  return null;
}

function humanizeKey(key: string): string {
  return key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function findSpecificValue(
  records: Record<string, unknown>[],
  aliases: readonly string[],
): string | null {
  for (const record of records) {
    for (const [key, value] of Object.entries(record)) {
      if (aliases.includes(normalizeKey(key))) {
        const displayed = displayValue(value);
        if (displayed) return displayed;
      }
    }
  }
  return null;
}

function itemSpecificRows(
  raw: Record<string, unknown>,
  fallback: Record<string, string>,
): SpecificRow[] {
  const nestedSpecifics = isRecord(raw.item_specifics)
    ? raw.item_specifics
    : {};
  const records = [nestedSpecifics, raw];
  const rows: SpecificRow[] = [];
  const knownAliases = new Set<string>(
    COMMON_SPECIFICS.flatMap((specific) => [...specific.aliases]),
  );
  const displayedLabels = new Set<string>();

  for (const specific of COMMON_SPECIFICS) {
    const value =
      findSpecificValue(records, specific.aliases) ??
      (specific.label === "Language" ? null : fallback[specific.label]);
    if (value) {
      rows.push({ label: specific.label, value });
      displayedLabels.add(normalizeKey(specific.label));
    }
  }

  const remainingEntries = [
    ...Object.entries(nestedSpecifics),
    ...Object.entries(raw).filter(
      ([key]) => !["itemspecifics", "keywords"].includes(normalizeKey(key)),
    ),
  ];
  for (const [key, value] of remainingEntries) {
    if (knownAliases.has(normalizeKey(key))) continue;
    const displayed = displayValue(value);
    const label = humanizeKey(key);
    if (displayed && !displayedLabels.has(normalizeKey(label))) {
      rows.push({ label, value: displayed });
      displayedLabels.add(normalizeKey(label));
    }
  }

  return rows;
}

function draftKeywords(raw: Record<string, unknown>): string[] {
  if (!Array.isArray(raw.keywords)) return [];
  return Array.from(
    new Set(
      raw.keywords
        .filter(
          (keyword): keyword is string =>
            typeof keyword === "string" && keyword.trim().length > 0,
        )
        .map((keyword) => keyword.trim()),
    ),
  );
}

function CopyIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className="h-4 w-4"
    >
      <rect x="8" y="8" width="11" height="11" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </svg>
  );
}

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

  const newestDraftId =
    drafts.reduce<ListingDraft | null>((newest, draft) => {
      if (!newest) return draft;
      return Date.parse(draft.created_at) > Date.parse(newest.created_at)
        ? draft
        : newest;
    }, null)?.id ?? null;
  const specifics = selectedDraft
    ? itemSpecificRows(selectedDraft.item_specifics_json, {
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
                aria-pressed={selectedDraft?.id === draft.id}
                title={`Select draft ${drafts.length - index}, version ${draft.version}`}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400 ${
                  selectedDraft?.id === draft.id
                    ? "border-green-400 bg-green-950/40 text-green-200"
                    : draft.id === newestDraftId
                      ? "border-sky-600 text-zinc-200 hover:border-sky-400"
                      : "border-zinc-700 text-zinc-300 hover:border-zinc-500"
                }`}
              >
                <span>
                  Draft {drafts.length - index} · v{draft.version}
                </span>
                {draft.id === newestDraftId && (
                  <span className="rounded-full bg-sky-900 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
                    Latest
                  </span>
                )}
                {selectedDraft?.id === draft.id && (
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-green-300">
                    Selected
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedDraft && form && !editing && (
        <div className="mt-5 rounded-xl border border-zinc-700 bg-zinc-900 p-4 md:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-zinc-400">
              <span>{selectedDraft.status}</span>
              <span aria-hidden="true">·</span>
              <span>Version {selectedDraft.version}</span>
              {selectedDraft.id === newestDraftId && (
                <span className="rounded-full bg-sky-900 px-2 py-0.5 font-semibold text-sky-200">
                  Latest
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setEditing(true);
                setError(null);
                setSuccess(null);
              }}
              title="Edit the selected draft"
              className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-green-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
            >
              Edit Draft
            </button>
          </div>

          <div className="mt-5 grid min-w-0 gap-6 lg:grid-cols-[minmax(180px,0.7fr)_minmax(0,1.7fr)]">
            <aside className="min-w-0">
              {cardImageUrl ? (
                <button
                  ref={imageTriggerRef}
                  type="button"
                  onClick={() => setImagePreviewOpen(true)}
                  title="Open larger card image"
                  aria-label={`Open larger preview of ${cardName}`}
                  className="group block w-full overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
                >
                  {/* Signed URLs are short-lived and generated at runtime. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={cardImageUrl}
                    alt={`${cardName} card`}
                    className="max-h-[28rem] w-full object-contain transition group-hover:scale-[1.02]"
                  />
                </button>
              ) : (
                <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-950/60 p-4 text-center text-sm text-zinc-500">
                  No stored card image
                </div>
              )}
              {cardImageUrl && (
                <p className="mt-2 text-center text-xs text-zinc-500">
                  Select image to enlarge
                </p>
              )}
            </aside>

            <article className="min-w-0">
              <section>
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    Listing Title
                  </h4>
                  <button
                    type="button"
                    onClick={() => void copyText("Title", selectedDraft.title)}
                    title="Copy listing title"
                    aria-label="Copy listing title"
                    className="rounded-md p-2 text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400"
                  >
                    <CopyIcon />
                  </button>
                </div>
                <p className="mt-1 break-words text-lg font-semibold leading-7 text-zinc-100">
                  {selectedDraft.title}
                </p>
              </section>

              <section className="mt-5">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    Description
                  </h4>
                  <button
                    type="button"
                    onClick={() =>
                      void copyText("Description", selectedDraft.description)
                    }
                    title="Copy listing description"
                    aria-label="Copy listing description"
                    className="rounded-md p-2 text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400"
                  >
                    <CopyIcon />
                  </button>
                </div>
                <p className="mt-2 max-w-prose whitespace-pre-wrap break-words text-sm leading-6 text-zinc-200">
                  {selectedDraft.description}
                </p>
              </section>

              <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
                <div className="rounded-lg bg-zinc-950/70 p-3">
                  <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                    Suggested Price
                  </dt>
                  <dd className="mt-1 text-base font-semibold text-amber-300">
                    Price not verified
                  </dd>
                </div>
                <div className="rounded-lg bg-zinc-950/70 p-3">
                  <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">
                    Category Suggestion
                  </dt>
                  <dd className="mt-1 break-words text-zinc-200">
                    {selectedDraft.category_suggestion ?? "Not suggested"}
                  </dd>
                </div>
              </dl>

              <p
                role="note"
                className="mt-3 rounded-lg border border-amber-700/70 bg-amber-950/30 px-3 py-2 text-sm text-amber-200"
              >
                AI price is not market-verified. Check recent sold listings
                before listing.
              </p>

              <section className="mt-6">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Item Specifics
                </h4>
                {specifics.length > 0 ? (
                  <div className="mt-2 overflow-hidden rounded-lg border border-zinc-700">
                    <table className="w-full table-fixed text-left text-sm">
                      <tbody className="divide-y divide-zinc-800">
                        {specifics.map((specific) => (
                          <tr key={specific.label}>
                            <th
                              scope="row"
                              className="w-2/5 bg-zinc-950/60 px-3 py-2 align-top font-medium text-zinc-400"
                            >
                              {specific.label}
                            </th>
                            <td className="break-words px-3 py-2 text-zinc-200">
                              {specific.value}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-zinc-500">
                    No item specifics available.
                  </p>
                )}
              </section>

              <section className="mt-6">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    Keywords
                  </h4>
                  {keywords.length > 0 && (
                    <button
                      type="button"
                      onClick={() =>
                        void copyText("Keywords", keywords.join(", "))
                      }
                      title="Copy all keywords"
                      className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400"
                    >
                      <CopyIcon />
                      Copy all
                    </button>
                  )}
                </div>
                {keywords.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {keywords.map((keyword) => (
                      <span
                        key={keyword}
                        className="max-w-full break-words rounded-full border border-zinc-600 bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-zinc-500">
                    No keywords available.
                  </p>
                )}
              </section>

              <details className="mt-6 rounded-lg border border-zinc-700 bg-zinc-950/50">
                <summary className="cursor-pointer px-3 py-2 text-sm text-zinc-300 focus-visible:outline-2 focus-visible:outline-green-400">
                  View Raw JSON
                </summary>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all border-t border-zinc-800 p-3 text-xs text-zinc-300">
                  {JSON.stringify(selectedDraft.item_specifics_json, null, 2)}
                </pre>
              </details>

              <div className="mt-6 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void copyText("Title", selectedDraft.title)}
                  title="Copy listing title"
                  className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
                >
                  Copy Title
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void copyText("Description", selectedDraft.description)
                  }
                  title="Copy listing description"
                  className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
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
                  title="Copy the complete draft as JSON"
                  className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
                >
                  Copy JSON
                </button>
              </div>
            </article>
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
              title="Save draft changes"
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
              title="Discard unsaved draft changes"
              className="rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:border-zinc-500 disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {imagePreviewOpen && cardImageUrl && (
        <div
          role="presentation"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
          onClick={closeImagePreview}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${cardName} image preview`}
            className="relative max-h-full max-w-4xl"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              autoFocus
              onClick={closeImagePreview}
              title="Close image preview"
              className="absolute right-2 top-2 z-10 rounded-md bg-black/80 px-3 py-2 text-sm font-medium text-white hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
            >
              Close
            </button>
            {/* Signed URLs are short-lived and generated at runtime. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={cardImageUrl}
              alt={`${cardName} enlarged card`}
              className="max-h-[90vh] max-w-full rounded-lg object-contain shadow-2xl"
            />
          </div>
        </div>
      )}
    </section>
  );
}
