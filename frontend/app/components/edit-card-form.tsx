import { CARD_STATUSES, SUPPORTED_GAMES } from "@/types/cards";
import type { DetectedGame, EditCardForm, InventoryCard } from "@/types/cards";

type EditCardFormProps = {
  card: InventoryCard;
  editForm: EditCardForm;
  editSavingId: string | null;
  editError: string | null;
  onUpdate: <FieldName extends keyof EditCardForm>(
    field: FieldName,
    value: EditCardForm[FieldName],
  ) => void;
  onSave: (cardId: string) => void;
  onCancel: () => void;
};

export function EditCardFormView({
  card,
  editForm,
  editSavingId,
  editError,
  onUpdate,
  onSave,
  onCancel,
}: EditCardFormProps) {
  return (
    <div className="mt-4 border-t border-zinc-800 pt-4">
      <p className="mb-3 text-sm text-zinc-400">
        Update the saved inventory details.
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Game</span>
          <select
            value={editForm.detected_game}
            onChange={(event) =>
              onUpdate("detected_game", event.target.value as DetectedGame)
            }
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          >
            {SUPPORTED_GAMES.map((game) => (
              <option key={game} value={game}>
                {game}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Card Name</span>
          <input
            value={editForm.card_name}
            onChange={(event) => onUpdate("card_name", event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Set</span>
          <input
            value={editForm.set}
            onChange={(event) => onUpdate("set", event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Card Number</span>
          <input
            value={editForm.card_number}
            onChange={(event) => onUpdate("card_number", event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Rarity</span>
          <input
            value={editForm.rarity}
            onChange={(event) => onUpdate("rarity", event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Condition</span>
          <input
            value={editForm.condition_guess}
            onChange={(event) => onUpdate("condition_guess", event.target.value)}
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
            onChange={(event) => onUpdate("price_amount", event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Currency</span>
          <input
            value={editForm.currency}
            maxLength={3}
            onChange={(event) =>
              onUpdate("currency", event.target.value.toUpperCase())
            }
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-400">Status</span>
          <select
            value={editForm.status}
            onChange={(event) =>
              onUpdate("status", event.target.value as InventoryCard["status"])
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
          onClick={() => onSave(card.id)}
          disabled={editSavingId === card.id}
          className="rounded-lg bg-green-500 px-4 py-2 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
        >
          {editSavingId === card.id ? "Saving…" : "Save Changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
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
  );
}
