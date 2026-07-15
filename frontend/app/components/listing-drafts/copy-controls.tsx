import type { ListingDraft } from "@/types/listings";

export function CopyIcon() {
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

type CopyControlsProps = {
  draft: ListingDraft;
  onCopy: (label: string, value: string) => void;
};

export function CopyControls({ draft, onCopy }: CopyControlsProps) {
  return (
    <div className="mt-6 flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onCopy("Title", draft.title)}
        title="Copy listing title"
        className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
      >
        Copy Title
      </button>
      <button
        type="button"
        onClick={() => onCopy("Description", draft.description)}
        title="Copy listing description"
        className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
      >
        Copy Description
      </button>
      <button
        type="button"
        onClick={() => onCopy("JSON", JSON.stringify(draft, null, 2))}
        title="Copy the complete draft as JSON"
        className="rounded-md border border-zinc-600 px-3 py-1.5 text-sm text-zinc-100 hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-400"
      >
        Copy JSON
      </button>
    </div>
  );
}
