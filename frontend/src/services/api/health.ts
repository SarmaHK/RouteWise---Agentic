/**
 * `GET /health` — liveness probe (A1 brief §12). Mounted at the ROOT path, not under `/api`
 * (backend/app/api/health.py; ARCHITECTURE §11 cloud-ready). Proves the backend is reachable.
 */

import type { HealthResponse } from '../../types/api';
import { request } from './client';

/** Fetch backend health. @throws {ApiError} when unreachable or non-2xx. */
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { method: 'GET' });
}
