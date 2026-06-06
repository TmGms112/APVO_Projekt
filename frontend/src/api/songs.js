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

export function songStreamUrl(id) {
  return apiUrl(`/songs/${id}/stream`);
}

export async function getSongs(limit = 1000) {
  const res = await fetch(apiUrl(`/songs/?limit=${limit}`));
  return handleJson(res);
}

export async function searchSongs({ title = "", artist = "" }) {
  const params = new URLSearchParams();
  if (title) params.append("title", title);
  if (artist) params.append("artist", artist);

  const res = await fetch(apiUrl(`/songs/search?${params.toString()}`));
  return handleJson(res);
}

export async function uploadSong(file, { title = "", artist = "" } = {}) {
  const form = new FormData();
  form.append("file", file);

  const params = new URLSearchParams();
  if (title) params.append("title", title);
  if (artist) params.append("artist", artist);

  const qs = params.toString();
  const url = apiUrl(`/songs/upload${qs ? `?${qs}` : ""}`);

  const res = await fetch(url, {
    method: "POST",
    body: form,
  });

  return handleJson(res);
}

export async function updateSongMeta(id, meta) {
  const res = await fetch(apiUrl(`/songs/${id}/meta`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(meta),
  });

  return handleJson(res);
}

export async function deleteSong(id) {
  const res = await fetch(apiUrl(`/songs/${id}`), {
    method: "DELETE",
  });

  return handleJson(res);
}
