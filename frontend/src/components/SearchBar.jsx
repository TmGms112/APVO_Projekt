import { useState } from "react";

export default function SearchBar({ onSearch, onClear }) {
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch({ title: title.trim(), artist: artist.trim() });
  };

  const handleClear = () => {
    setTitle("");
    setArtist("");
    onClear();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-sm text-white/60">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-xl bg-black/25 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
            placeholder="e.g. Halo"
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm text-white/60">Artist</label>
          <input
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
            className="w-full rounded-xl bg-black/25 border border-white/10 px-3 py-2 text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-green-500/50"
            placeholder="e.g. Beyoncé"
          />
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          className="px-5 py-2 rounded-full bg-white text-black font-semibold hover:bg-white/90 transition"
        >
          Search
        </button>

        <button
          type="button"
          onClick={handleClear}
          className="px-5 py-2 rounded-full bg-white/10 border border-white/10 hover:bg-white/15 transition"
        >
          Clear
        </button>
      </div>
    </form>
  );
}
