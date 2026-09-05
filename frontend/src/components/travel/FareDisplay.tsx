/**
 * FareDisplay — a fare/budget figure (DESIGN_SYSTEM §12.10, registry §13.3). Money is data →
 * mono (§14), colored by budget fit (under → success, over → error). Color is never the only
 * signal: RouteCard pairs it with a text "Budget: Within/Over" metric (§15). The amount and the
 * fit are produced by the backend; this component only formats them via the shared `formatMoney`
 * service (§13.4) and never recomputes a fare or a budget decision (A8 brief §23).
 */

import { formatMoney } from '../../services/format';

import './FareDisplay.css';

export type BudgetStatus = 'within' | 'over' | 'unknown';

export interface FareDisplayProps {
  amount: number;
  currency?: string;
  /** Budget fit → color. Derived by the backend (`within_budget`); the UI never recomputes it. */
  budgetStatus?: BudgetStatus;
  className?: string;
}

export function FareDisplay({
  amount,
  currency = 'LKR',
  budgetStatus = 'unknown',
  className,
}: FareDisplayProps) {
  const classes = ['fare', `fare--${budgetStatus}`, className ?? ''].filter(Boolean).join(' ');

  return <span className={classes}>{formatMoney(amount, currency)}</span>;
}
