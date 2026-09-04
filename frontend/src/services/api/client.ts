/**
 * Single backend client (ARCHITECTURE §3.2–§3.3): the ONLY module that calls `fetch`.
 * Components/hooks go through `services/api/*` and never fetch directly.
 *
 * Responsibilities: base URL + JSON headers + timeout, response parsing, and normalizing every
 * failure mode (HTTP error envelope, network error, timeout) into one typed `ApiError` so callers
 * handle a single shape (DEVELOPMENT_RULES rule 15). No secrets live here — `config/env.ts`
 * exposes only VITE_*-prefixed values.
 */

import { env } from '../../config/env';

/** Default per-request timeout (ms). A1 endpoints are local and fast. */
const DEFAULT_TIMEOUT_MS = 10000;

/** The backend's structured error envelope (API_CONTRACTS §5). */
interface ErrorEnvelope {
  status?: string;
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    retryable?: boolean;
  };
}

/** Normalized error thrown by the client for every failure mode. */
export class ApiError extends Error {
  /** Stable machine code clients may branch on (API_CONTRACTS §5), e.g. `network_error`. */
  readonly code: string;
  /** HTTP status, or 0 when the request never completed (network failure / timeout). */
  readonly status: number;
  /** Whether a retry could plausibly succeed. */
  readonly retryable: boolean;
  /** Non-sensitive technical context from the server, when present. */
  readonly details?: unknown;

  constructor(
    message: string,
    options: { code?: string; status?: number; retryable?: boolean; details?: unknown } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = options.code ?? 'unknown_error';
    this.status = options.status ?? 0;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/** `fetch` options plus a JSON-serializable body and an optional timeout override. */
interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Plain object stringified here, so callers never build JSON by hand. */
  body?: unknown;
  /** Per-request timeout override (ms). */
  timeoutMs?: number;
}

/**
 * Perform a JSON request against the backend and return the parsed body.
 *
 * @throws {ApiError} on timeout, network failure, non-2xx response, or malformed JSON.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...init } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw await toApiError(response);
    }
    if (response.status === 204) {
      return undefined as T; // No Content.
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(`Request to ${path} timed out after ${timeoutMs}ms.`, {
        code: 'timeout',
        retryable: true,
      });
    }
    // Network error / backend down — the most common local-dev failure.
    throw new ApiError(
      `Could not reach the backend at ${env.apiBaseUrl}. Is it running (uvicorn app.main:app)?`,
      { code: 'network_error', retryable: true },
    );
  } finally {
    clearTimeout(timer);
  }
}

/** Convert a non-2xx response into an `ApiError`, reading the §5 envelope when present. */
async function toApiError(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope | undefined;
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = undefined; // Non-JSON error body; fall back to the status text.
  }
  const detail = envelope?.error;
  return new ApiError(detail?.message || response.statusText || `HTTP ${response.status}`, {
    code: detail?.code ?? 'http_error',
    status: response.status,
    retryable: detail?.retryable ?? response.status >= 500,
    details: detail?.details,
  });
}
