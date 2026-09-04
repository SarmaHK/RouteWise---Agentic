/**
 * Frontend runtime configuration (Phase A1 foundation).
 *
 * Only VITE_*-prefixed variables are exposed to the client by Vite — so NOTHING secret can
 * live here (docs/DEVELOPMENT_RULES.md -> Environment & secrets). The API base URL defaults to
 * the local FastAPI backend (docs/ARCHITECTURE.md §3.3).
 */
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const env = {
  /** Backend base URL, with any trailing slash(es) stripped. */
  apiBaseUrl: rawBaseUrl.replace(/\/+$/, ''),
} as const;
