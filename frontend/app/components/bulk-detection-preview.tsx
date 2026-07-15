"use client";

import { useEffect, useState } from "react";

import { detectCardsInImage } from "@/lib/api/detection";
import { errorMessage, reportUnexpectedError } from "@/lib/api/client";
import { BROWSER_PREVIEW_TYPES, IMAGE_ACCEPT, validateImageFile } from "@/lib/validation/images";
import type { CardDetectionResponse } from "@/types/detection";

export function BulkDetectionPreview() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [result, setResult] = useState<CardDetectionResponse | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [detectionError, setDetectionError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (selectedImage) {
        URL.revokeObjectURL(selectedImage);
      }
    };
  }, [selectedImage]);

  function selectImageFile(file: File): boolean {
    setUploadError(null);
    setDetectionError(null);
    setResult(null);

    const validationError = validateImageFile(file);
    if (validationError) {
      setSelectedFile(null);
      setSelectedImage(null);
      setUploadError(validationError);
      return false;
    }

    const contentType = file.type.trim().toLowerCase();
    setSelectedFile(file);
    setSelectedImage(
      BROWSER_PREVIEW_TYPES.has(contentType) ? URL.createObjectURL(file) : null,
    );
    return true;
  }

  function handleImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!selectImageFile(file)) {
      event.currentTarget.value = "";
    }
  }

  function handleImageDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      selectImageFile(file);
    }
  }

  async function detectCards() {
    if (!selectedFile) {
      setDetectionError("Choose a multi-card image before detecting.");
      return;
    }

    setDetecting(true);
    setDetectionError(null);
    setResult(null);

    try {
      const detectionResult = await detectCardsInImage(selectedFile);
      setResult(detectionResult);
    } catch (error) {
      reportUnexpectedError("Bulk detection error:", error);
      setDetectionError(errorMessage(error, "Unable to detect cards."));
    } finally {
      setDetecting(false);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-950/50 p-5">
      <div>
        <h2 className="text-2xl font-bold">Bulk Detection Preview</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Experimental OpenCV baseline. Detects rectangular card candidates only;
          it does not analyze, save, or list cards.
        </p>
      </div>

      <label
        htmlFor="bulk-card-upload"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleImageDrop}
        className="mt-4 block cursor-pointer rounded-xl border-2 border-dashed border-zinc-700 p-6 text-center transition hover:border-green-500"
      >
        <input
          id="bulk-card-upload"
          type="file"
          accept={IMAGE_ACCEPT}
          onChange={handleImageUpload}
          className="hidden"
        />

        {selectedImage ? (
          // Local object URLs are generated from the selected file before upload.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={selectedImage}
            alt="Selected bulk detection source"
            className="mx-auto max-h-80 rounded-xl border border-zinc-700"
          />
        ) : selectedFile ? (
          <>
            <p className="text-lg font-medium">Selected: {selectedFile.name}</p>
            <p className="mt-2 text-sm text-zinc-500">
              A normalized JPEG will be sent for deterministic detection.
            </p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium">Upload Multi-Card Image</p>
            <p className="mt-2 text-sm text-zinc-500">
              JPEG, PNG, WebP, HEIC, HEIF, AVIF • 25 MB maximum
            </p>
          </>
        )}
      </label>

      {uploadError && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {uploadError}
        </p>
      )}

      <button
        type="button"
        onClick={() => void detectCards()}
        disabled={!selectedFile || detecting}
        className="mt-4 w-full rounded-xl bg-green-500 py-3 font-semibold text-black transition hover:bg-green-400 disabled:bg-zinc-600 disabled:text-zinc-300"
      >
        {detecting ? "Detecting…" : "Detect Cards"}
      </button>

      {detectionError && (
        <p role="alert" className="mt-3 text-sm text-red-400">
          {detectionError}
        </p>
      )}

      {result && (
        <div className="mt-5 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">Detection Result</h3>
              <p className="text-sm text-zinc-400">
                {result.count} candidate{result.count === 1 ? "" : "s"} detected
                in {result.image_width} × {result.image_height}
              </p>
            </div>
          </div>

          {/* Debug preview is generated in-memory by the backend. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={result.debug_image}
            alt="Detected card candidates with bounding boxes"
            className="mt-4 max-h-[42rem] w-full rounded-lg border border-zinc-700 object-contain"
          />

          {result.detections.length > 0 ? (
            <div className="mt-4 overflow-x-auto rounded-lg border border-zinc-800">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-950 text-xs uppercase tracking-wide text-zinc-400">
                  <tr>
                    <th className="px-3 py-2">#</th>
                    <th className="px-3 py-2">x</th>
                    <th className="px-3 py-2">y</th>
                    <th className="px-3 py-2">width</th>
                    <th className="px-3 py-2">height</th>
                    <th className="px-3 py-2">heuristic confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {result.detections.map((detection) => (
                    <tr key={detection.index}>
                      <td className="px-3 py-2 text-zinc-200">
                        {detection.index}
                      </td>
                      <td className="px-3 py-2 text-zinc-300">{detection.x}</td>
                      <td className="px-3 py-2 text-zinc-300">{detection.y}</td>
                      <td className="px-3 py-2 text-zinc-300">
                        {detection.width}
                      </td>
                      <td className="px-3 py-2 text-zinc-300">
                        {detection.height}
                      </td>
                      <td className="px-3 py-2 text-zinc-300">
                        {detection.confidence.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-zinc-500">
              No rectangular card candidates were found.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
