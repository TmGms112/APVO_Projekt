import { useEffect, useState } from "react";

export default function EditMetadataModal({ open, song, onClose, onSave }) {
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [genre, setGenre] = useState("");
  const [year, setYear] = useState("");

  useEffect(() => {
    if (!song) return;
    setTitle(song.title || "");
    setArtist(song.artist || "");
    setGenre(song.genre || "");
    setYear(song.year ? String(song.year) : "");
  }, [song]);

  if (!open || !song) return null;

  const handleSubmit = (e) => {
    e.preventDefault();

    const parsedYear = year.trim() ? Number(year) : undefined;
    if (year.trim() && Number.isNaN(parsedYear)) {
      alert("Year must be a number.");
      return;
    }

    onSave({
      ...song,
      title: title.trim(),
      artist: artist.trim(),
      genre: genre.trim(),
      year: parsedYear,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />

      <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-neutral-950 shadow-[0_20px_60px_rgba(0,0,0,0.6)] p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">Edit metadata</h2>
            <p className="text-sm text-white/60">Update title, artist, genre and year</p>
          </div>

          <button
            onClick={onClose}
            className="px-3 py-2 rounded-full bg-white/10 border border-white/10 hover:bg-white/15 transition"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <Field label="Title">
            <input
              className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Song title"
              required
            />
          </Field>

          <Field label="Artist">
            <input
              className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              placeholder="Artist name"
            />
          </Field>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Genre">
              <input
                className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                placeholder="e.g. Pop"
              />
            </Field>

            <Field label="Year">
              <input
                className="w-full rounded-xl bg-black/30 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder="e.g. 2024"
              />
            </Field>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 rounded-full bg-white/10 border border-white/10 hover:bg-white/15 transition"
            >
              Cancel
            </button>

            <button
              type="submit"
              className="px-5 py-2 rounded-full bg-green-500 text-black font-semibold hover:bg-green-400 transition"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm text-white/60">{label}</span>
      {children}
    </label>
  );
}
