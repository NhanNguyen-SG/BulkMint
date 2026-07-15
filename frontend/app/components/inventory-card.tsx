import { EditCardFormView } from "./edit-card-form";
import { ListingDraftPanel } from "./listing-drafts/listing-draft-panel";

import type { EditCardForm, InventoryCard as InventoryCardType } from "@/types/cards";

type RemovalAction = "archive" | "delete";

type InventoryCardProps = {
  card: InventoryCardType;
  draftCardId: string | null;
  editingCardId: string | null;
  editForm: EditCardForm | null;
  editSavingId: string | null;
  editError: string | null;
  editSuccessId: string | null;
  removingCardId: string | null;
  removalAction: RemovalAction | null;
  removalError: string | null;
  removalErrorCardId: string | null;
  onStartEditing: (card: InventoryCardType) => void;
  onUpdateEditField: <FieldName extends keyof EditCardForm>(
    field: FieldName,
    value: EditCardForm[FieldName],
  ) => void;
  onSaveEdit: (cardId: string) => void;
  onCancelEditing: () => void;
  onOpenDrafts: (cardId: string) => void;
  onCloseDrafts: () => void;
  onArchive: (cardId: string) => void;
  onDelete: (cardId: string) => void;
};

export function InventoryCard({
  card,
  draftCardId,
  editingCardId,
  editForm,
  editSavingId,
  editError,
  editSuccessId,
  removingCardId,
  removalAction,
  removalError,
  removalErrorCardId,
  onStartEditing,
  onUpdateEditField,
  onSaveEdit,
  onCancelEditing,
  onOpenDrafts,
  onCloseDrafts,
  onArchive,
  onDelete,
}: InventoryCardProps) {
  const actionDisabled = editSavingId === card.id || removingCardId === card.id;

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          {card.image_url && (
            // Signed URLs are short-lived and generated at runtime.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={card.image_url}
              alt={`${card.card_name} card`}
              className="h-20 w-16 rounded-md border border-zinc-700 object-cover"
            />
          )}
          <div className="min-w-0">
            <p className="break-words font-semibold text-lg">{card.card_name}</p>
            <p className="break-words text-zinc-400">
              {card.set} • {card.rarity}
            </p>
            <p className="mt-1 text-sm text-zinc-500">{card.detected_game}</p>
            <p className="text-green-400 mt-2">{card.suggested_price}</p>
            <p className="mt-1 text-xs uppercase tracking-wide text-zinc-500">
              {card.status}
            </p>
          </div>
        </div>

        <div className="flex-shrink-0 sm:text-right">
          <div className="text-sm text-zinc-500">#{card.card_number}</div>
          <button
            type="button"
            onClick={() => onStartEditing(card)}
            disabled={actionDisabled}
            className="mt-3 rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-200 transition hover:border-green-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => onOpenDrafts(card.id)}
            disabled={actionDisabled}
            className="mt-2 block w-full rounded-md border border-green-700/60 px-3 py-1.5 text-sm text-green-300 transition hover:border-green-500 hover:text-green-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Generate Draft
          </button>
          {card.status !== "archived" && (
            <button
              type="button"
              onClick={() => onArchive(card.id)}
              disabled={actionDisabled}
              className="mt-2 block w-full rounded-md border border-amber-600/40 px-3 py-1.5 text-sm text-amber-300 transition hover:border-amber-400 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {removingCardId === card.id && removalAction === "archive"
                ? "Archiving…"
                : "Archive"}
            </button>
          )}
          <button
            type="button"
            onClick={() => onDelete(card.id)}
            disabled={actionDisabled}
            className="mt-2 block w-full rounded-md border border-red-700/50 px-3 py-1.5 text-sm text-red-300 transition hover:border-red-500 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {removingCardId === card.id && removalAction === "delete"
              ? "Deleting…"
              : "Delete"}
          </button>
        </div>
      </div>

      {draftCardId === card.id && (
        <ListingDraftPanel
          cardId={card.id}
          cardGame={card.detected_game}
          cardName={card.card_name}
          cardImageUrl={card.image_url}
          cardSet={card.set}
          cardNumber={card.card_number}
          cardRarity={card.rarity}
          cardCondition={card.condition_guess}
          onClose={onCloseDrafts}
        />
      )}

      {editingCardId === card.id && editForm && (
        <EditCardFormView
          card={card}
          editForm={editForm}
          editSavingId={editSavingId}
          editError={editError}
          onUpdate={onUpdateEditField}
          onSave={onSaveEdit}
          onCancel={onCancelEditing}
        />
      )}

      {editSuccessId === card.id && editingCardId !== card.id && (
        <p className="mt-3 text-sm text-green-400">Inventory card updated.</p>
      )}
      {removalError && removalErrorCardId === card.id && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {removalError}
        </p>
      )}
    </div>
  );
}
