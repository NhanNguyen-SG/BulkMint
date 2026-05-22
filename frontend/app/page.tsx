"use client";

import { useState } from "react";

type AnalysisResult = {
  card_name: string;
  set: string;
  card_number: string;
  rarity: string;
  condition_guess: string;
  suggested_price: string;
  ebay_title: string;
  ebay_description: string;
};

export default function Home() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  function handleImageUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setSelectedImage(URL.createObjectURL(file));
    setResult(null);
  }

  async function analyzeCard() {
    if (!selectedFile) {
      alert("Please upload a card image first.");
      return;
    }

    setLoading(true);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("http://localhost:8000/analyze-card", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      setResult(data);
    } catch (error) {
      alert("Error analyzing card. Make sure backend is running.");
    } finally {
      setLoading(false);
    }
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

        <button
          onClick={analyzeCard}
          disabled={loading}
          className="w-full mt-6 bg-green-500 hover:bg-green-400 disabled:bg-zinc-600 disabled:text-zinc-300 text-black font-semibold py-3 rounded-xl transition"
        >
          {loading ? "Analyzing..." : "Analyze Card"}
        </button>

        {result && (
          <div className="mt-6 bg-zinc-950 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-xl font-semibold mb-3">Analysis Result</h2>
            <p><span className="text-zinc-400">Card:</span> {result.card_name}</p>
            <p><span className="text-zinc-400">Set:</span> {result.set}</p>
            <p><span className="text-zinc-400">Rarity:</span> {result.rarity}</p>
            <p><span className="text-zinc-400">Suggested Price:</span> {result.suggested_price}</p>
            <p className="text-sm text-zinc-500 mt-3">{result.status}</p>
            <p><span className="text-zinc-400">Card Number:</span> {result.card_number}</p>
            <p><span className="text-zinc-400">Condition Guess:</span> {result.condition_guess}</p>

          <div className="mt-5 border-t border-zinc-800 pt-4">
            <h3 className="font-semibold mb-2">eBay Draft</h3>
            <p><span className="text-zinc-400">Title:</span> {result.ebay_title}</p>
            <p className="mt-2"><span className="text-zinc-400">Description:</span> {result.ebay_description}</p>
</div>
          </div>
        )}
      </div>
    </main>
  );
}