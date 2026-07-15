import type { RefObject } from "react";

type ListingImagePreviewProps = {
  cardName: string;
  cardImageUrl: string | null;
  imagePreviewOpen: boolean;
  imageTriggerRef: RefObject<HTMLButtonElement | null>;
  onOpen: () => void;
  onClose: () => void;
};

export function ListingImagePreview({
  cardName,
  cardImageUrl,
  imagePreviewOpen,
  imageTriggerRef,
  onOpen,
  onClose,
}: ListingImagePreviewProps) {
  return (
    <aside className="min-w-0">
      {cardImageUrl ? (
        <button
          ref={imageTriggerRef}
          type="button"
          onClick={onOpen}
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
      {imagePreviewOpen && cardImageUrl && (
        <ListingImagePreviewModal
          cardName={cardName}
          cardImageUrl={cardImageUrl}
          onClose={onClose}
        />
      )}
    </aside>
  );
}

type ListingImagePreviewModalProps = {
  cardName: string;
  cardImageUrl: string;
  onClose: () => void;
};

export function ListingImagePreviewModal({
  cardName,
  cardImageUrl,
  onClose,
}: ListingImagePreviewModalProps) {
  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
      onClick={onClose}
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
          onClick={onClose}
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
  );
}
