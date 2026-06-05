import { apiUrl } from "./config";

async function handleJson(res) {
  const text = await res.text();
  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const msg =
      (data && data.detail) ||
      (typeof data === "string" ? data : null) ||
      `Request failed (${res.status})`;
    throw new Error(msg);
  }

  return data;
}

export async function trainModels() {
  const res = await fetch(apiUrl("/ml/train"), { method: "POST" });
  return handleJson(res);
}

export async function getMlStats() {
  const res = await fetch(apiUrl("/ml/stats"));
  return handleJson(res);
}

export async function getLatestModelRun() {
  const res = await fetch(apiUrl("/ml/model-runs/latest"));
  return handleJson(res);
}

export async function getPlaylists() {
  const res = await fetch(apiUrl("/ml/playlists"));
  return handleJson(res);
}

export async function getRecommendations(songId, limit = 5) {
  const res = await fetch(apiUrl(`/ml/recommendations/${songId}?limit=${limit}`));
  return handleJson(res);
}
