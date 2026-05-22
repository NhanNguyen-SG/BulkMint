export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
        
        <h1 className="text-4xl font-bold mb-2">
          BulkMint
        </h1>

        <p className="text-zinc-400 mb-8">
          AI-powered TCG listing assistant
        </p>

        <div className="border-2 border-dashed border-zinc-700 rounded-xl p-12 text-center hover:border-green-500 transition cursor-pointer">
          <p className="text-lg font-medium">
            Upload Card Image
          </p>

          <p className="text-sm text-zinc-500 mt-2">
            Drag & drop or click to upload
          </p>
        </div>

        <button className="w-full mt-6 bg-green-500 hover:bg-green-400 text-black font-semibold py-3 rounded-xl transition">
          Analyze Card
        </button>

      </div>
    </main>
  );
}