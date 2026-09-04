/**
 * `POST /api/route/plan` — the reserved primary endpoint (API_CONTRACTS §2).
 *
 * In A1 the backend returns an HONEST foundation stub (status IDLE, no fabricated route); the
 * real planning/decision engine lands in A2–A9. This module is the single caller of that
 * endpoint — components never fetch it directly (ARCHITECTURE §3.2).
 */

import type { PlanRequest, PlanResponse } from '../../types/api';
import { request } from './client';

/** Submit a travel request; returns the agent's (A1: foundation-stub) plan response. */
export function planRoute(payload: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/api/route/plan', { method: 'POST', body: payload });
}
