import SongCard from "./SongCard";

export default function SongList({ songs, onEdit, onRecommend }) {
  if (!songs || songs.length === 0) {
    return <p className="text-white/60">No songs found.</p>;
  }

  return (
    <div className="space-y-3">
      {songs.map((song) => (
        <SongCard key={song.id} song={song} onEdit={onEdit} onRecommend={onRecommend} />
      ))}
    </div>
  );
}
