import type { ListingDraft } from "@/types/listings";

type DraftVersionSelectorProps = {
  drafts: ListingDraft[];
  selectedDraftId: string | null;
  newestDraftId: string | null;
  onSelect: (draft: ListingDraft) => void;
};

export function DraftVersionSelector({
  drafts,
  selectedDraftId,
  newestDraftId,
  onSelect,
}: DraftVersionSelectorProps) {
  if (drafts.length === 0) return null;

  return (
    <div className="mt-4">
      <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
        Draft versions
      </p>
      <div className="flex flex-wrap gap-2">
        {drafts.map((draft, index) => (
          <button
            key={draft.id}
            type="button"
            onClick={() => onSelect(draft)}
            aria-pressed={selectedDraftId === draft.id}
            title={`Select draft ${drafts.length - index}, version ${draft.version}`}
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400 ${
              selectedDraftId === draft.id
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
            {selectedDraftId === draft.id && (
              <span className="text-[10px] font-semibold uppercase tracking-wide text-green-300">
                Selected
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
