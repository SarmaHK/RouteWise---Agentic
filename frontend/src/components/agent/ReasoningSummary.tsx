/**
 * ReasoningSummary — the concise human explanation of the decision (DESIGN_SYSTEM §12.9,
 * registry §13.3), shown at COMPLETED. It renders the backend's top-level `reasoning` string
 * verbatim; the frontend never generates its own rationale or invents reasons (A8 brief §14).
 */

import './ReasoningSummary.css';

export interface ReasoningSummaryProps {
  summary: string;
  className?: string;
}

export function ReasoningSummary({ summary, className }: ReasoningSummaryProps) {
  const classes = ['decision-reasoning', className ?? ''].filter(Boolean).join(' ');

  return (
    <p className={classes}>
      <span className="decision-reasoning__label">In short:</span> {summary}
    </p>
  );
}
