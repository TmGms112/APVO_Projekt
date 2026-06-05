export default function SongCard({ song, onEdit, onRecommend }) {
  const status = song.analysisStatus || "pending";

  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 hover:bg-black/30 transition p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-semibold truncate">{song.title}</p>
          <StatusPill status={status} duration={song.duration} />
        </div>

        <p className="text-sm text-white/60 truncate">{song.artist}</p>

        <div className="mt-2 flex flex-wrap gap-2">
          {song.genre && <Pill>{song.genre}</Pill>}
          {song.year && <Pill>{song.year}</Pill>}
          {song.cluster !== undefined && song.cluster !== null && <Pill>Cluster {song.cluster}</Pill>}
          {song.hash && <Pill className="max-w-[280px] truncate"># {song.hash}</Pill>}
        </div>
      </div>

      <div className="flex items-center justify-between md:justify-end gap-2">
        <button
          onClick={() => onRecommend?.(song)}
          disabled={status !== "done"}
          className="px-4 py-2 rounded-full bg-green-500 text-black font-semibold hover:bg-green-400 transition disabled:opacity-40"
        >
          Next
        </button>
        <button
          onClick={() => onEdit?.(song)}
          className="px-4 py-2 rounded-full bg-white/10 border border-white/10 hover:bg-white/15 transition"
        >
          Edit
        </button>
      </div>
    </div>
  );
}

function StatusPill({ status, duration }) {
  if (status === "done") {
    return (
      <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-green-500/15 text-green-300 border border-green-500/25">
        {duration ? `${duration}s` : "Done"}
      </span>
    );
  }

  if (status === "failed") {
    return (
      <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-200 border border-red-500/25">
        Failed
      </span>
    );
  }

  return (
    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-200 border border-yellow-500/25">
      Pending
    </span>
  );
}

function Pill({ children, className = "" }) {
  return (
    <span
      className={
        "px-2.5 py-1 rounded-full text-xs bg-white/10 border border-white/10 text-white/80 " +
        className
      }
      title={typeof children === "string" ? children : undefined}
    >
      {children}
    </span>
  );
}
