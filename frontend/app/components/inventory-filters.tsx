import { CARD_STATUSES, SUPPORTED_GAMES } from "@/types/cards";
import type { InventoryFilters } from "@/types/cards";

type InventoryFiltersProps = {
  filters: InventoryFilters;
  inventoryLoading: boolean;
  onApply: (event: React.FormEvent<HTMLFormElement>) => void;
  onClear: () => void;
  onUpdate: <FieldName extends keyof InventoryFilters>(
    field: FieldName,
    value: InventoryFilters[FieldName],
  ) => void;
};

export function InventoryFiltersForm({
  filters,
  inventoryLoading,
  onApply,
  onClear,
  onUpdate,
}: InventoryFiltersProps) {
  return (
    <form
      onSubmit={onApply}
      className="mb-4 grid gap-3 rounded-xl border border-zinc-800 bg-zinc-950 p-4 md:grid-cols-2"
    >
      <label className="text-sm md:col-span-2">
        <span className="mb-1 block text-zinc-400">Search card name or game</span>
        <input
          type="search"
          value={filters.q}
          onChange={(event) => onUpdate("q", event.target.value)}
          placeholder="e.g. Charizard or Pokemon"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
        />
      </label>
      <label className="text-sm">
        <span className="mb-1 block text-zinc-400">Game</span>
        <select
          value={filters.detected_game}
          onChange={(event) =>
            onUpdate(
              "detected_game",
              event.target.value as InventoryFilters["detected_game"],
            )
          }
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
        >
          <option value="">All games</option>
          {SUPPORTED_GAMES.map((game) => (
            <option key={game} value={game}>
              {game}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        <span className="mb-1 block text-zinc-400">Set</span>
        <input
          value={filters.set_name}
          onChange={(event) => onUpdate("set_name", event.target.value)}
          placeholder="All sets"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
        />
      </label>
      <label className="text-sm">
        <span className="mb-1 block text-zinc-400">Rarity</span>
        <input
          value={filters.rarity}
          onChange={(event) => onUpdate("rarity", event.target.value)}
          placeholder="All rarities"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
        />
      </label>
      <label className="text-sm">
        <span className="mb-1 block text-zinc-400">Status</span>
        <select
          value={filters.status}
          onChange={(event) =>
            onUpdate("status", event.target.value as InventoryFilters["status"])
          }
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-white"
        >
          <option value="">All active inventory</option>
          {CARD_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </label>
      <div className="flex gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={inventoryLoading}
          className="rounded-lg bg-green-500 px-4 py-2 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
        >
          {inventoryLoading ? "Searching…" : "Search"}
        </button>
        <button
          type="button"
          onClick={onClear}
          disabled={inventoryLoading}
          className="rounded-lg border border-zinc-700 px-4 py-2 text-zinc-200 transition hover:border-zinc-500 hover:text-white disabled:opacity-60"
        >
          Clear Filters
        </button>
      </div>
    </form>
  );
}
