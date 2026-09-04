/**
 * `POST /api/route/plan` — the reserved primary endpoint (API_CONTRACTS §2).
 *
 * In A2 the backend UNDERSTANDS the request (natural-language extraction into a TravelRequest,
 * status UNDERSTANDING) and plans no route; the real planning/decision engine lands in A3–A9.
 * This module is the single caller of that endpoint — components never fetch it directly
 * (ARCHITECTURE §3.2).
 */

import type { PlanRequest, PlanResponse } from '../../types/api';
import { request } from './client';

/** Submit a travel request; returns the agent's (A2: understanding-only) plan response. */
export function planRoute(payload: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/api/route/plan', { method: 'POST', body: payload });
}
