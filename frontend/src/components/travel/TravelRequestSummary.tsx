/**
 * TravelRequestSummary — the request the agent understood (DESIGN_SYSTEM §12; the A2 output).
 * Echoes the normalized TravelRequest fields as data (mono) and lists any assumptions the
 * extractor recorded. A missing field reads "Not specified" — the summary never invents a value
 * the backend did not return (§16). Presentational only; no extraction or decision logic here
 * (A8 brief §23). Added to the registry (§13.3) in A8 — genuinely new & reusable (§13.5).
 */

import type { TravelRequest } from '../../types/api';

import './TravelRequestSummary.css';

/** A missing optional value is shown honestly — never fabricated (§12.8 empty). */
function display(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null;
  return String(value);
}

export interface TravelRequestSummaryProps {
  request: TravelRequest;
  className?: string;
}

export function TravelRequestSummary({ request, className }: TravelRequestSummaryProps) {
  const rows: { label: string; value: string | null }[] = [
    { label: 'Origin', value: display(request.origin) },
    { label: 'Destination', value: display(request.destination) },
    {
      label: 'Budget',
      value: request.budget != null ? `${request.budget} ${request.currency ?? 'LKR'}` : null,
    },
    { label: 'Luggage', value: display(request.luggage) },
    { label: 'Walking', value: display(request.walking_preference) },
    { label: 'Departure', value: display(request.departure_time) },
    { label: 'Arrive by', value: display(request.arrival_deadline) },
  ];

  const assumptions = request.assumptions ?? [];
  const classes = ['travel-request-summary', className ?? ''].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <dl className="travel-request">
        {rows.map((row) => (
          <div className="travel-request__row" key={row.label}>
            <dt className="travel-request__label">{row.label}</dt>
            <dd className="travel-request__value">
              {row.value ? (
                <span className="rw-mono">{row.value}</span>
              ) : (
                <span className="travel-request__empty">Not specified</span>
              )}
            </dd>
          </div>
        ))}
      </dl>

      {assumptions.length > 0 && (
        <ul className="assumptions">
          {assumptions.map((assumption) => (
            <li key={assumption} className="rw-meta">
              Assumption: {assumption}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
