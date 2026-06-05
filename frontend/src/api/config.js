export const API_BASE_URL = "/api";

/**
 * Helper: pravi punu URL adresu za API.
 * Primjer: apiUrl("/songs") -> http://localhost:8000/songs
 */
export function apiUrl(path) {
  if (!path.startsWith("/")) return `${API_BASE_URL}/${path}`;
  return `${API_BASE_URL}${path}`;
}
