export default function AnalyticsDashboard({
  stats,
  modelRun,
  playlists,
  recommendations,
  selectedSong,
  onPlaySong,
  onPlayPlaylist,
  playingSongId,
}) {
  if (!stats && !modelRun && !playlists) {
    return <p className="text-white/60">No ML results loaded yet.</p>;
  }

  const models = modelRun?.models_tested || [];
  const selectedModel = modelRun?.selected_model;
  const playlistItems = playlists?.playlists || [];
  const silhouetteValues = models
    .map((model) => model.metrics?.silhouette_score)
    .filter((value) => value !== null && value !== undefined && !Number.isNaN(Number(value)))
    .map(Number);

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

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
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
            <Metric
              label="Max playlist"
              value={formatPercent(selectedModel.playlist_quality?.max_cluster_fraction)}
            />
          </div>

          {modelRun?.preprocessing && (
            <p className="text-xs text-white/45">
              Features were scaled, acoustic analysis was weighted higher, PCA reduced the model space
              to {modelRun.preprocessing.pca_components || modelRun.model_feature_count} dimensions,
              and model selection penalized one oversized playlist.
            </p>
          )}
        </div>
      )}

      {models.length > 0 && (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
          <h3 className="font-semibold mb-3">Model comparison</h3>
          <div className="space-y-3">
            {models.map((model) => (
              <ScoreBar key={model.model_name} model={model} silhouettes={silhouetteValues} />
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
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold truncate">{playlist.name}</div>
                    <span className="text-xs text-white/60">{playlist.song_count} songs</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onPlayPlaylist?.(playlist)}
                    className="shrink-0 px-3 py-1.5 rounded-full bg-green-500 text-black text-sm font-semibold hover:bg-green-400 transition"
                  >
                    Play
                  </button>
                </div>
                <p className="mt-2 text-sm text-white/60">{playlist.description}</p>
                <div className="mt-3 space-y-1.5">
                  {playlist.songs.slice(0, 8).map((song) => {
                    const isPlaying = playingSongId === String(song.id);
                    return (
                      <div
                        key={song.id}
                        className="flex items-center justify-between gap-2 text-sm text-white/80"
                      >
                        <div className="min-w-0 truncate">
                          {song.title} <span className="text-white/40">- {song.artist}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => onPlaySong?.(song, playlist.songs)}
                          className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold transition ${
                            isPlaying
                              ? "bg-white text-black"
                              : "bg-white/10 text-white hover:bg-white/15 border border-white/10"
                          }`}
                        >
                          {isPlaying ? "Playing" : "Play"}
                        </button>
                      </div>
                    );
                  })}
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
                <div className="flex items-center gap-3 md:justify-end">
                  <div className="text-sm text-white/60 md:text-right">
                    <div>{Math.round(item.similarity * 100)}% similar</div>
                    <div>{item.reason}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onPlaySong?.(item.song)}
                    className="px-3 py-1.5 rounded-full bg-white text-black text-sm font-semibold hover:bg-white/90 transition"
                  >
                    Play
                  </button>
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

function ScoreBar({ model, silhouettes }) {
  const silhouette = Number(model.metrics?.silhouette_score ?? 0);
  const min = Math.min(...silhouettes, silhouette);
  const max = Math.max(...silhouettes, silhouette);
  const range = max - min;
  const width = range > 0 ? 22 + ((silhouette - min) / range) * 78 : Math.max(8, Math.min(100, silhouette * 100));

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span>{model.model_name}</span>
        <span className="text-white/60">Silhouette {formatNumber(silhouette)}</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full bg-green-400" style={{ width: `${Math.max(8, width)}%` }} />
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-white/45">
        <span>{model.description}</span>
        <span>{model.cluster_count} playlists</span>
        <span>DB {formatNumber(model.metrics?.davies_bouldin_score)}</span>
        <span>Max playlist {formatPercent(model.playlist_quality?.max_cluster_fraction)}</span>
      </div>
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

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Math.round(Number(value) * 100)}%`;
}
