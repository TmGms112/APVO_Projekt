import { useState } from "react";
import { uploadSong } from "../api/songs";

export default function UploadForm({ onUpload }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    try {
      setLoading(true);
      setError("");

      const created = await uploadSong(file, {
        title: file?.name || "",
        artist: "",
      });

      const first = Array.isArray(created) ? created[0] : created;
      const song = normalizeCreatedSong(first, file);

      onUpload(song);
      setFile(null);
    } catch (e) {
      setError(e.message || "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block">
        <div className="rounded-2xl border border-dashed border-white/15 bg-black/20 hover:bg-black/25 transition p-4 cursor-pointer">
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="font-medium">Choose an audio file</div>
              <div className="text-sm text-white/60">Click to browse audio files</div>
            </div>

            <span className="px-3 py-1 rounded-full bg-white/10 border border-white/10 text-sm">
              Browse
            </span>
          </div>

          <input
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            disabled={loading}
          />
        </div>

        {file && (
          <div className="mt-2 text-sm text-white/70">
            Selected: <span className="font-medium text-white">{file.name}</span>
          </div>
        )}
      </label>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 text-red-100 px-3 py-2 text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={!file || loading}
          className="px-5 py-2 rounded-full bg-green-500 text-black font-semibold hover:bg-green-400 transition disabled:opacity-50"
        >
          {loading ? "Uploading..." : "Upload"}
        </button>

        <div className="text-xs text-white/50">
          Upload stores the audio in MongoDB and queues it for analysis.
        </div>
      </div>
    </form>
  );
}

function normalizeCreatedSong(created, file) {
  const id =
    created?.id ||
    created?._id ||
    created?.songId ||
    created?.song_id ||
    created?.key ||
    Date.now().toString();

  return {
    id: String(id),
    title: created?.title || created?.name || file?.name || "Untitled",
    artist: created?.artist || "Unknown",
    genre: created?.genre,
    year: created?.year,
    analysisStatus: created?.analysisStatus || created?.analysis_status || "pending",
    duration: created?.duration || created?.duration_seconds || "pending",
    hash: created?.hash,
  };
}
