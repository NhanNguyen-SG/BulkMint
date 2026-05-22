"use client";

import { useState } from "react";

export default function Home() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  function handleImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) return;

    const imageUrl = URL.createObjectURL(file);
    setSelectedImage(imageUrl);
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
        <h1 className="text-4xl font-bold mb-2">BulkMint</h1>

        <p className="text-zinc-400 mb-8">
          AI-powered TCG listing assistant
        </p>

        <label
        htmlFor="card-upload"
          className="block border-2 border-dashed border-zinc-700 rounded-xl p-8 text-center hover:border-green-500 transition cursor-pointer"
>
          <input
            id="card-upload"
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="hidden"
          />

          {selectedImage ? (
            <img
              src={selectedImage}
              alt="Selected card"
              className="mx-auto max-h-80 rounded-xl border border-zinc-700"
            />
          ) : (
            <>
              <p className="text-lg font-medium">Upload Card Image</p>
              <p className="text-sm text-zinc-500 mt-2">
                Drag & drop or click to upload
              </p>
            </>
          )}
        </label>

        <button className="w-full mt-6 bg-green-500 hover:bg-green-400 text-black font-semibold py-3 rounded-xl transition">
          Analyze Card
        </button>
      </div>
    </main>
  );
}