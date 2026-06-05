export default function AnalyticsDashboard({
  stats,
  modelRun,
  playlists,
  recommendations,
  selectedSong,
}) {
  if (!stats && !modelRun && !playlists) {
    return <p className="text-white/60">No ML results loaded yet.</p>;
  }

  const models = modelRun?.models_tested || [];
  const selectedModel = modelRun?.selected_model;
  const playlistItems = playlists?.playlists || [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Songs" value={stats?.song_count ?? 0} />
        <Metric label="Analyzed" value={stats?.analyzed_song_count ?? 0} />
        <Metric label="Avg tempo" value={formatNumber(stats?.average_tempo, " BPM")} />
        <Metric label="Duplicates" value={stats?.duplicate_count ?? 0} />
      </div>

      {selectedModel && (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
          <div className="flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
            <div>
              <h3 className="font-semibold">Selected model</h3>
              <p className="text-sm text-white/60">{selectedModel.model_name}</p>
            </div>
            <div className="text-sm text-white/60">{modelRun?.song_count} songs trained</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Metric
              label="Silhouette"
              value={formatNumber(selectedModel.metrics?.silhouette_score)}
            />
            <Metric
              label="Davies-Bouldin"
              value={formatNumber(selectedModel.metrics?.davies_bouldin_score)}
            />
            <Metric
              label="Calinski-Harabasz"
              value={formatNumber(selectedModel.metrics?.calinski_harabasz_score)}
            />
          </div>
        </div>
      )}

      {models.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
          <h3 className="font-semibold mb-3">Model comparison</h3>
          <div className="space-y-3">
            {models.map((model) => (
              <ScoreBar key={model.model_name} model={model} />
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Histogram title="Tempo distribution" data={stats?.tempo_histogram || []} suffix=" BPM" />
        <Histogram title="Energy distribution" data={stats?.energy_histogram || []} />
        <Histogram title="Duration distribution" data={stats?.duration_histogram || []} suffix="s" />
      </div>

      {playlistItems.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
          <h3 className="font-semibold">Generated playlists</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {playlistItems.map((playlist) => (
              <div key={playlist.cluster} className="rounded-xl border border-white/10 bg-white/5 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold">{playlist.name}</div>
                  <span className="text-xs text-white/60">{playlist.song_count} songs</span>
                </div>
                <p className="mt-1 text-sm text-white/60">{playlist.description}</p>
                <div className="mt-3 space-y-1">
                  {playlist.songs.slice(0, 5).map((song) => (
                    <div key={song.id} className="text-sm text-white/80 truncate">
                      {song.title} <span className="text-white/40">- {song.artist}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {recommendations?.recommendations?.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
          <div>
            <h3 className="font-semibold">Recommended next songs</h3>
            <p className="text-sm text-white/60">
              Based on {selectedSong?.title || recommendations.song?.title}
            </p>
          </div>
          <div className="space-y-2">
            {recommendations.recommendations.map((item) => (
              <div
                key={item.song.id}
                className="rounded-xl border border-white/10 bg-white/5 p-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2"
              >
                <div>
                  <div className="font-medium">{item.song.title}</div>
                  <div className="text-sm text-white/60">{item.song.artist}</div>
                </div>
                <div className="text-sm text-white/60 md:text-right">
                  <div>{Math.round(item.similarity * 100)}% similar</div>
                  <div>{item.reason}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="text-xs uppercase text-white/45">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value ?? "-"}</div>
    </div>
  );
}

function ScoreBar({ model }) {
  const silhouette = model.metrics?.silhouette_score ?? 0;
  const width = Math.max(8, Math.min(100, Math.round(((silhouette + 1) / 2) * 100)));

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span>{model.model_name}</span>
        <span className="text-white/60">Silhouette {formatNumber(silhouette)}</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full bg-green-400" style={{ width: `${width}%` }} />
      </div>
      <p className="mt-1 text-xs text-white/45">{model.description}</p>
    </div>
  );
}

function Histogram({ title, data, suffix = "" }) {
  const max = Math.max(1, ...data.map((item) => item.count));

  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <h3 className="font-semibold mb-3">{title}</h3>
      {data.length === 0 ? (
        <p className="text-sm text-white/60">No data</p>
      ) : (
        <div className="space-y-2">
          {data.map((item) => (
            <div key={`${item.min}-${item.max}`}>
              <div className="flex justify-between text-xs text-white/50 mb-1">
                <span>
                  {item.min}-{item.max}{suffix}
                </span>
                <span>{item.count}</span>
              </div>
              <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-white/60"
                  style={{ width: `${Math.max(6, (item.count / max) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(2)}${suffix}`;
}
