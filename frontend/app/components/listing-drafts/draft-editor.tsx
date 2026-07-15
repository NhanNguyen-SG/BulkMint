import { DRAFT_STATUSES } from "@/types/listings";
import type { DraftForm, ListingDraft, ListingDraftStatus } from "@/types/listings";

type DraftEditorProps = {
  selectedDraft: ListingDraft;
  form: DraftForm;
  saving: boolean;
  onUpdate: <FieldName extends keyof DraftForm>(
    field: FieldName,
    value: DraftForm[FieldName],
  ) => void;
  onSave: () => void;
  onCancel: () => void;
};

export function DraftEditor({
  form,
  saving,
  onUpdate,
  onSave,
  onCancel,
}: DraftEditorProps) {
  return (
    <div className="mt-4 space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <label className="block text-sm">
        <span className="mb-1 block text-zinc-400">Title</span>
        <input
          value={form.title}
          onChange={(event) => onUpdate("title", event.target.value)}
          className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-zinc-400">Description</span>
        <textarea
          rows={5}
          value={form.description}
          onChange={(event) => onUpdate("description", event.target.value)}
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
            onChange={(event) => onUpdate("price_amount", event.target.value)}
            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Currency</span>
          <input
            maxLength={3}
            value={form.currency}
            onChange={(event) =>
              onUpdate("currency", event.target.value.toUpperCase())
            }
            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Status</span>
          <select
            value={form.status}
            onChange={(event) =>
              onUpdate("status", event.target.value as ListingDraftStatus)
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
          <span className="mb-1 block text-zinc-400">Category suggestion</span>
          <input
            value={form.category_suggestion}
            onChange={(event) =>
              onUpdate("category_suggestion", event.target.value)
            }
            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2"
          />
        </label>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-zinc-400">Item specifics JSON</span>
        <textarea
          rows={7}
          spellCheck={false}
          value={form.item_specifics_json}
          onChange={(event) =>
            onUpdate("item_specifics_json", event.target.value)
          }
          className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-xs"
        />
      </label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          title="Save draft changes"
          className="rounded-md bg-green-500 px-4 py-2 text-sm font-semibold text-black hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
        >
          {saving ? "Saving…" : "Save Draft"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          title="Discard unsaved draft changes"
          className="rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:border-zinc-500 disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
