/**
 * Data formatters (DESIGN_SYSTEM §13.4: "Formatters — LKR currency, durations, times,
 * distances — live in frontend services/utils, not inside components").
 *
 * Every value here is a pure presentation helper: it formats a number/string the backend
 * already produced. It NEVER derives a decision, a score, or a route fact (rule 13 /
 * A8 brief §23: no business logic in the frontend). Extracted verbatim from the A3–A7 App
 * shell so the components share one source instead of re-declaring formatters inline.
 */

/** Money is data → grouped and currency-prefixed (DESIGN_SYSTEM §14: data is mono). */
export function formatMoney(value: number, currency = 'LKR'): string {
  return `${currency} ${Math.round(value).toLocaleString('en-US')}`;
}

/** Route fares are always LKR in the mock dataset (API_CONTRACTS §3). */
export function formatLkr(value: number): string {
  return formatMoney(value, 'LKR');
}

/** Durations read as h/m for legibility — still honest, still mock. */
export function formatMinutes(value: number): string {
  const mins = Math.round(value);
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  return hours > 0 ? `${hours}h ${rest}m` : `${rest} min`;
}

/** Walking distance to one decimal place (the granularity the mock data carries). */
export function formatKm(value: number): string {
  return `${value.toFixed(1)} km`;
}

/**
 * A short, human-safe message for any thrown value (no stack traces in the UI —
 * A8 brief §24). `ApiError`/`Error` messages are already user-facing; anything else
 * collapses to a generic string.
 */
export function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}
