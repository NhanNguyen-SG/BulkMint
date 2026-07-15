import Link from "next/link";

import { InventoryCard } from "./inventory-card";

import type {
  EditCardForm,
  InventoryCard as InventoryCardType,
  InventoryFilters,
} from "@/types/cards";

type RemovalAction = "archive" | "delete";

type InventoryListProps = {
  inventory: InventoryCardType[];
  inventoryLoading: boolean;
  inventoryError: string | null;
  inventoryAuthRequired: boolean;
  appliedFilters: InventoryFilters;
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

export function InventoryList({
  inventory,
  inventoryLoading,
  inventoryError,
  inventoryAuthRequired,
  appliedFilters,
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
}: InventoryListProps) {
  return (
    <>
      {inventoryLoading && (
        <p className="text-sm text-zinc-500">Loading inventory…</p>
      )}
      {inventoryError && (
        <p role="alert" className="text-sm text-red-400">
          {inventoryError}
        </p>
      )}
      {inventoryAuthRequired && (
        <p className="text-sm text-zinc-400">
          Please{" "}
          <Link href="/login" className="text-green-400 hover:text-green-300">
            log in
          </Link>{" "}
          to view your inventory.
        </p>
      )}
      {!inventoryLoading &&
        !inventoryError &&
        !inventoryAuthRequired &&
        inventory.length === 0 && (
          <p className="text-sm text-zinc-500">
            {Object.values(appliedFilters).some(Boolean)
              ? "No cards match these filters."
              : "No saved cards yet."}
          </p>
        )}

      {inventory.length > 0 && (
        <div className="space-y-4">
          {inventory.map((card) => (
            <InventoryCard
              key={card.id}
              card={card}
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
              onStartEditing={onStartEditing}
              onUpdateEditField={onUpdateEditField}
              onSaveEdit={onSaveEdit}
              onCancelEditing={onCancelEditing}
              onOpenDrafts={onOpenDrafts}
              onCloseDrafts={onCloseDrafts}
              onArchive={onArchive}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </>
  );
}
