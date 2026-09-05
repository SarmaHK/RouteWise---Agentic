/**
 * Public surface of the frontend data layer (ARCHITECTURE §3.1: `services/api` is THE only
 * caller of the backend). Import from `services/api` — not from the individual modules — so the
 * boundary stays single and obvious. Shapes mirror docs/API_CONTRACTS.md.
 */

export { ApiError, request } from './client';
export { getHealth } from './health';
export { planRoute } from './routePlan';
export {
  replanRoute,
  prepareBookingHold,
  getTravelPass,
  injectDisruption,
  restoreDisruption,
  getDisruptionStatus,
} from './execution';
export type { BookingHoldResponse, TravelPassData } from './execution';
