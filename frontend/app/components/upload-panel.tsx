import { IMAGE_ACCEPT } from "@/lib/validation/images";

type UploadPanelProps = {
  selectedFile: File | null;
  selectedImage: string | null;
  uploadError: string | null;
  analyzing: boolean;
  saving: boolean;
  onImageUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onImageDrop: (event: React.DragEvent<HTMLLabelElement>) => void;
  onAnalyze: () => void;
};

export function UploadPanel({
  selectedFile,
  selectedImage,
  uploadError,
  analyzing,
  saving,
  onImageUpload,
  onImageDrop,
  onAnalyze,
}: UploadPanelProps) {
  return (
    <>
      <label
        htmlFor="card-upload"
        onDragOver={(event) => event.preventDefault()}
        onDrop={onImageDrop}
        className="block border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center hover:border-green-500 transition cursor-pointer"
      >
        <input
          id="card-upload"
          type="file"
          accept={IMAGE_ACCEPT}
          onChange={onImageUpload}
          className="hidden"
        />

        {selectedImage ? (
          // Local object URLs are generated from the selected file before upload.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={selectedImage}
            alt="Selected card"
            className="mx-auto max-h-80 rounded-xl border border-zinc-700"
          />
        ) : selectedFile ? (
          <>
            <p className="text-lg font-medium">Selected: {selectedFile.name}</p>
            <p className="text-sm text-zinc-500 mt-2">
              A normalized JPEG preview will be created after upload.
            </p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium">Upload Card Image</p>
            <p className="text-sm text-zinc-500 mt-2">
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
        onClick={onAnalyze}
        disabled={!selectedFile || analyzing || saving}
        className="w-full mt-6 bg-green-500 hover:bg-green-400 disabled:bg-zinc-600 disabled:text-zinc-300 text-black font-semibold py-3 rounded-xl transition"
      >
        {analyzing ? "Analyzing…" : "Analyze Card"}
      </button>
    </>
  );
}
