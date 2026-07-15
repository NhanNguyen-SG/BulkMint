import type { CardAnalysisResult } from "@/types/cards";

type AnalysisReviewProps = {
  result: CardAnalysisResult;
  saving: boolean;
  saved: boolean;
  saveError: string | null;
  onSave: () => void;
};

export function AnalysisReview({
  result,
  saving,
  saved,
  saveError,
  onSave,
}: AnalysisReviewProps) {
  return (
    <div className="mt-6 bg-zinc-950 border border-zinc-800 rounded-xl p-5">
      <h2 className="text-xl font-semibold mb-1">Review Analysis</h2>
      <p className="mb-3 text-sm text-zinc-500">
        Confirm these details before saving.
      </p>
      <p>
        <span className="text-zinc-400">Game:</span> {result.detected_game}
      </p>
      <p>
        <span className="text-zinc-400">Card:</span> {result.card_name}
      </p>
      <p>
        <span className="text-zinc-400">Set:</span> {result.set}
      </p>
      <p>
        <span className="text-zinc-400">Rarity:</span> {result.rarity}
      </p>
      <p>
        <span className="text-zinc-400">Suggested Price:</span>{" "}
        {result.suggested_price}
      </p>
      <p>
        <span className="text-zinc-400">Card Number:</span>{" "}
        {result.card_number}
      </p>
      <p>
        <span className="text-zinc-400">Condition Guess:</span>{" "}
        {result.condition_guess}
      </p>

      <div className="mt-5 border-t border-zinc-800 pt-4">
        <h3 className="font-semibold mb-2">eBay Draft</h3>
        <p>
          <span className="text-zinc-400">Title:</span> {result.ebay_title}
        </p>
        <p className="mt-2">
          <span className="text-zinc-400">Description:</span>{" "}
          {result.ebay_description}
        </p>
      </div>

      <button
        type="button"
        onClick={onSave}
        disabled={saving || saved}
        className="mt-5 w-full rounded-lg bg-green-500 py-2.5 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-700 disabled:text-zinc-300"
      >
        {saving ? "Saving…" : saved ? "Saved" : "Save to Inventory"}
      </button>

      {saveError && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {saveError}
        </p>
      )}
      {saved && (
        <p className="mt-3 text-sm text-green-400">Card saved to inventory.</p>
      )}
    </div>
  );
}
