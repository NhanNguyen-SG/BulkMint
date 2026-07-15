import { CopyControls, CopyIcon } from "./copy-controls";
import { ItemSpecificsTable } from "./item-specifics-table";
import { ListingImagePreview } from "./listing-image-preview";
import { PriceWarning } from "./price-warning";

import type { RefObject } from "react";
import type { ListingDraft } from "@/types/listings";

type SpecificRow = {
  label: string;
  value: string;
};

type DraftDisplayProps = {
  draft: ListingDraft;
  newestDraftId: string | null;
  cardName: string;
  cardImageUrl: string | null;
  specifics: SpecificRow[];
  keywords: string[];
  imagePreviewOpen: boolean;
  imageTriggerRef: RefObject<HTMLButtonElement | null>;
  onEdit: () => void;
  onCopy: (label: string, value: string) => void;
  onOpenImagePreview: () => void;
  onCloseImagePreview: () => void;
};

export function DraftDisplay({
  draft,
  newestDraftId,
  cardName,
  cardImageUrl,
  specifics,
  keywords,
  imagePreviewOpen,
  imageTriggerRef,
  onEdit,
  onCopy,
  onOpenImagePreview,
  onCloseImagePreview,
}: DraftDisplayProps) {
  return (
    <>
      <div className="mt-5 rounded-xl border border-zinc-700 bg-zinc-900 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-zinc-400">
            <span>{draft.status}</span>
            <span aria-hidden="true">·</span>
            <span>Version {draft.version}</span>
            {draft.id === newestDraftId && (
              <span className="rounded-full bg-sky-900 px-2 py-0.5 font-semibold text-sky-200">
                Latest
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onEdit}
            title="Edit the selected draft"
            className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-green-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
          >
            Edit Draft
          </button>
        </div>

        <div className="mt-5 grid min-w-0 gap-6 lg:grid-cols-[minmax(180px,0.7fr)_minmax(0,1.7fr)]">
          <ListingImagePreview
            cardName={cardName}
            cardImageUrl={cardImageUrl}
            imagePreviewOpen={imagePreviewOpen}
            imageTriggerRef={imageTriggerRef}
            onOpen={onOpenImagePreview}
            onClose={onCloseImagePreview}
          />

          <article className="min-w-0">
            <section>
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Listing Title
                </h4>
                <button
                  type="button"
                  onClick={() => onCopy("Title", draft.title)}
                  title="Copy listing title"
                  aria-label="Copy listing title"
                  className="rounded-md p-2 text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400"
                >
                  <CopyIcon />
                </button>
              </div>
              <p className="mt-1 break-words text-lg font-semibold leading-7 text-zinc-100">
                {draft.title}
              </p>
            </section>

            <section className="mt-5">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Description
                </h4>
                <button
                  type="button"
                  onClick={() => onCopy("Description", draft.description)}
                  title="Copy listing description"
                  aria-label="Copy listing description"
                  className="rounded-md p-2 text-zinc-300 hover:bg-zinc-800 hover:text-white focus-visible:outline-2 focus-visible:outline-green-400"
                >
                  <CopyIcon />
                </button>
              </div>
              <p className="mt-2 max-w-prose whitespace-pre-wrap break-words text-sm leading-6 text-zinc-200">
                {draft.description}
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
                  {draft.category_suggestion ?? "Not suggested"}
                </dd>
              </div>
            </dl>

            <PriceWarning />
            <ItemSpecificsTable specifics={specifics} />

            <section className="mt-6">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  Keywords
                </h4>
                {keywords.length > 0 && (
                  <button
                    type="button"
                    onClick={() => onCopy("Keywords", keywords.join(", "))}
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
                {JSON.stringify(draft.item_specifics_json, null, 2)}
              </pre>
            </details>

            <CopyControls draft={draft} onCopy={onCopy} />
          </article>
        </div>
      </div>

    </>
  );
}
