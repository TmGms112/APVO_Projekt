import { useMemo, useState } from "react";
import UploadForm from "../components/UploadForm";
import SongList from "../components/SongList";
import SearchBar from "../components/SearchBar";
import EditMetadataModal from "../components/EditMetadataModal";
import AnalyticsDashboard from "../components/AnalyticsDashboard";
import { getSongs, searchSongs, updateSongMeta } from "../api/songs";
import {
  getLatestModelRun,
  getMlStats,
  getPlaylists,
  getRecommendations,
  trainModels,
} from "../api/ml";

export default function Home() {
  const [songs, setSongs] = useState([
    {
      id: "1",
      title: "Mock Song 1",
      artist: "Mock Artist",
      analysisStatus: "pending",
    },
    {
      id: "2",
      title: "Halo",
      artist: "Beyonce",
      analysisStatus: "done",
      duration: 215,
      genre: "pop",
    },
    {
      id: "3",
      title: "Hello",
      artist: "Adele",
      analysisStatus: "done",
      duration: 295,
    },
  ]);

  const [filters, setFilters] = useState({ title: "", artist: "" });
  const [error, setError] = useState("");
  const [editingSong, setEditingSong] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlStats, setMlStats] = useState(null);
  const [modelRun, setModelRun] = useState(null);
  const [playlists, setPlaylists] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [selectedSong, setSelectedSong] = useState(null);

  const filteredSongs = useMemo(() => {
    const t = (filters.title || "").toLowerCase();
    const a = (filters.artist || "").toLowerCase();

    return songs.filter((s) => {
      const matchesTitle = t ? (s.title || "").toLowerCase().includes(t) : true;
      const matchesArtist = a ? (s.artist || "").toLowerCase().includes(a) : true;
      return matchesTitle && matchesArtist;
    });
  }, [songs, filters]);

  async function loadSongsFromApi() {
    try {
      setError("");
      const data = await getSongs();
      setSongs((Array.isArray(data) ? data : []).map(normalizeSongForUi));
      setFilters({ title: "", artist: "" });
    } catch (e) {
      setError(e.message || "Failed to load songs from API.");
    }
  }

  async function handleSearch(nextFilters) {
    setFilters(nextFilters);

    if (!nextFilters.title && !nextFilters.artist) return;

    try {
      setError("");
      const data = await searchSongs(nextFilters);
      setSongs((Array.isArray(data) ? data : []).map(normalizeSongForUi));
    } catch (e) {
      setError(e.message || "Failed to search songs from API.");
    }
  }

  async function loadMlDashboard() {
    try {
      setMlLoading(true);
      setError("");
      const [stats, latestRun, playlistData] = await Promise.all([
        getMlStats(),
        getLatestModelRun(),
        getPlaylists(),
      ]);
      setMlStats(stats);
      setModelRun(latestRun);
      setPlaylists(playlistData);
    } catch (e) {
      setError(e.message || "Failed to load ML dashboard.");
    } finally {
      setMlLoading(false);
    }
  }

  async function handleTrainModels() {
    try {
      setMlLoading(true);
      setError("");
      const latestRun = await trainModels();
      setModelRun(latestRun);
      await loadSongsFromApi();
      await loadMlDashboard();
    } catch (e) {
      setError(e.message || "Failed to train ML models.");
    } finally {
      setMlLoading(false);
    }
  }

  async function handleRecommend(song) {
    try {
      setMlLoading(true);
      setError("");
      setSelectedSong(song);
      const data = await getRecommendations(song.id, 5);
      setRecommendations(data);
    } catch (e) {
      setError(e.message || "Failed to generate recommendations.");
    } finally {
      setMlLoading(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold tracking-tight">Audio Library</h1>
          <p className="text-sm text-white/60">MongoDB-backed uploads, analysis and ML playlists</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadSongsFromApi}
            className="px-4 py-2 rounded-full bg-white/10 hover:bg-white/15 border border-white/10 transition"
          >
            Load from API
          </button>

          <div className="text-sm text-white/60 px-3 py-2 rounded-full border border-white/10 bg-white/5">
            {filteredSongs.length} result(s)
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 text-red-100 px-4 py-3">
          <div className="font-semibold">Network / API error</div>
          <div className="text-sm opacity-90">{error}</div>
        </div>
      )}

      <SectionCard title="Upload" subtitle="Add a new audio file to your library">
        <UploadForm onUpload={(song) => setSongs((prev) => [song, ...prev])} />
      </SectionCard>

      <SectionCard title="Search" subtitle="Search by title and artist">
        <SearchBar
          onSearch={handleSearch}
          onClear={() => setFilters({ title: "", artist: "" })}
        />
      </SectionCard>

      <SectionCard title="Machine Learning" subtitle="Train models, create playlists and recommend the next song">
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleTrainModels}
              disabled={mlLoading}
              className="px-5 py-2 rounded-full bg-green-500 text-black font-semibold hover:bg-green-400 transition disabled:opacity-50"
            >
              {mlLoading ? "Working..." : "Train Models"}
            </button>
            <button
              onClick={loadMlDashboard}
              disabled={mlLoading}
              className="px-5 py-2 rounded-full bg-white/10 border border-white/10 hover:bg-white/15 transition disabled:opacity-50"
            >
              Load ML Dashboard
            </button>
          </div>

          <AnalyticsDashboard
            stats={mlStats}
            modelRun={modelRun}
            playlists={playlists}
            recommendations={recommendations}
            selectedSong={selectedSong}
          />
        </div>
      </SectionCard>

      <SectionCard title="Songs" subtitle="Your current library">
        <SongList songs={filteredSongs} onEdit={(song) => setEditingSong(song)} onRecommend={handleRecommend} />
      </SectionCard>

      <EditMetadataModal
        open={!!editingSong}
        song={editingSong}
        onClose={() => setEditingSong(null)}
        onSave={async (updated) => {
          setSongs((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));

          try {
            setError("");
            await updateSongMeta(updated.id, {
              title: updated.title,
              artist: updated.artist,
              genre: updated.genre,
              year: updated.year,
            });
          } catch (e) {
            setError(e.message || "Failed to update metadata in API.");
          } finally {
            setEditingSong(null);
          }
        }}
      />
    </div>
  );
}

function SectionCard({ title, subtitle, children }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur px-5 py-5 shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
      <div className="flex flex-col gap-1 mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="text-sm text-white/60">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function normalizeSongForUi(raw) {
  const id = raw.id || raw._id || raw.songId || raw.song_id;
  return {
    id: String(id),
    title: raw.title || raw.name || raw.filename || "Untitled",
    artist: raw.artist || raw.audio_artist || "Unknown",
    genre: raw.genre || raw.audio_genre,
    year: raw.year || raw.audio_year,
    analysisStatus: raw.analysisStatus || raw.analysis_status || "pending",
    duration: raw.duration || raw.duration_seconds,
    hash: raw.hash,
    cluster: raw.ml_cluster,
  };
}
