/**
 * RouteCard — presents one route (DESIGN_SYSTEM §11.6/§12.10, registry §13.3). A left accent bar
 * (recommended → primary), totals in mono, a RouteTimeline of the route's legs, and the decision
 * detail the candidate actually carries: reasons/strengths/trade-offs, or — for an excluded
 * alternative — its structured constraint violations. It renders ONLY backend fields and tags them
 * MOCK (§16); it never computes a score, fare, rank, or budget verdict itself (A8 brief §23).
 * Reuses Badge + the FareDisplay/DelayBadge/RouteTimeline primitives (§21) — no forked card.
 *
 * Selection/booking props (`onSelect`, `selected`) are intentionally omitted: the A8 MVP is a
 * single plan flow with no booking (that is Workstream C — A8 brief §31).
 */

import type { ReactNode } from 'react';

import type { ConstraintViolation, Leg, Recommendation } from '../../types/api';
import { formatKm, formatMinutes } from '../../services/format';
import { Badge } from '../ui';
import { DelayBadge } from './DelayBadge';
import { FareDisplay } from './FareDisplay';
import { RouteTimeline } from './RouteTimeline';

import './RouteCard.css';

/** One observable figure on the card. The value is pre-formatted (data → mono, §14). */
interface Metric {
  label: string;
  value: ReactNode;
}

/** The figures a card shows — only what the candidate actually carries (§16: never invent one). */
function metricsFor(route: Recommendation): Metric[] {
  const metrics: Metric[] = [];
  if (route.total_duration_min != null) {
    metrics.push({ label: 'Duration', value: formatMinutes(route.total_duration_min) });
  }
  if (route.total_fare_lkr != null) {
    metrics.push({
      label: 'Fare',
      value: (
        <FareDisplay
          amount={route.total_fare_lkr}
          budgetStatus={
            route.within_budget == null ? 'unknown' : route.within_budget ? 'within' : 'over'
          }
        />
      ),
    });
  }
  if (route.transfers != null) {
    metrics.push({ label: 'Transfers', value: String(route.transfers) });
  }
  if (route.walking_km != null) {
    metrics.push({ label: 'Walking', value: formatKm(route.walking_km) });
  }
  // Budget fit is stated in WORDS as well as color — never color alone (§15).
  if (route.within_budget != null) {
    metrics.push({ label: 'Budget', value: route.within_budget ? 'Within' : 'Over' });
  }
  if (route.delay_risk && route.delay_risk !== 'none') {
    metrics.push({ label: 'Delay risk', value: <DelayBadge level={route.delay_risk} /> });
  }
  if (route.score != null) {
    metrics.push({ label: 'Fit score', value: route.score.toFixed(2) });
  }
  return metrics;
}

/** A recommendation's concise, observable reasons (A3 §8); falls back to the headline rationale. */
function reasonsFor(route: Recommendation): string[] {
  if (route.reasons && route.reasons.length > 0) return route.reasons;
  return route.rationale ? [route.rationale] : [];
}

export interface RouteCardProps {
  route: Recommendation;
  /** The chosen route — primary accent + "Recommended" badge + the leg timeline. */
  recommended?: boolean;
  /** Legs of the recommended route (the backend sends legs only for the chosen route). */
  legs?: Leg[];
  className?: string;
}

export function RouteCard({ route, recommended = false, legs = [], className }: RouteCardProps) {
  const classes = ['route-card', recommended ? 'route-card--recommended' : '', className ?? '']
    .filter(Boolean)
    .join(' ');

  const titleId = `route-${route.id}`;
  const metrics = metricsFor(route);
  const reasons = reasonsFor(route);
  const strengths = route.strengths ?? [];
  const tradeOffs = route.trade_offs ?? [];
  const violations: ConstraintViolation[] = route.constraint_violations ?? [];
  const excluded = route.valid === false;

  return (
    <article className={classes} aria-labelledby={titleId}>
      <header className="route-card__header">
        <div className="route-card__heading">
          <h3
            className={
              recommended ? 'route-card__title' : 'route-card__title route-card__title--alt'
            }
            id={titleId}
          >
            {recommended ? 'Recommended route' : route.id}
          </h3>
          <p className="route-card__summary">{route.summary}</p>
        </div>
        <div className="route-card__badges">
          {recommended && <Badge tone="primary">Recommended</Badge>}
          <Badge tone="secondary" mono>
            {route.data_source ?? 'mock'}
          </Badge>
        </div>
      </header>

      {metrics.length > 0 && (
        <dl className="route-card__metrics">
          {metrics.map((metric) => (
            <div className="metric" key={metric.label}>
              <dt className="metric__label">{metric.label}</dt>
              <dd className="metric__value rw-mono">{metric.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {/* Leg-by-leg detail (A7 populates `legs` for the recommended route from mock data). */}
      {recommended && legs.length > 0 && (
        <div className="route-card__legs">
          <h4 className="route-card__subtitle">Legs — mock route details</h4>
          <RouteTimeline legs={legs} />
        </div>
      )}

      {recommended && reasons.length > 0 && (
        <div className="route-card__reasons">
          <h4 className="route-card__subtitle">Why this route</h4>
          <ul className="reasons-list">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Alternatives (A6 §5/§11): excluded → structured violations; valid → strengths + trade-offs. */}
      {!recommended &&
        (excluded ? (
          <div className="route-card__tradeoffs">
            <h4 className="route-card__subtitle">Excluded — broke a hard constraint</h4>
            <ul className="reasons-list">
              {violations.length > 0
                ? violations.map((violation) => (
                    <li key={`${violation.type}:${violation.message}`}>
                      <span className="rw-mono">{violation.type}</span> — {violation.message}
                    </li>
                  ))
                : tradeOffs.map((tradeOff) => <li key={tradeOff}>{tradeOff}</li>)}
            </ul>
          </div>
        ) : (
          <>
            {strengths.length > 0 && (
              <div className="route-card__reasons">
                <h4 className="route-card__subtitle">Strengths</h4>
                <ul className="reasons-list">
                  {strengths.map((strength) => (
                    <li key={strength}>{strength}</li>
                  ))}
                </ul>
              </div>
            )}
            {tradeOffs.length > 0 && (
              <div className="route-card__tradeoffs">
                <h4 className="route-card__subtitle">Trade-offs vs recommendation</h4>
                <ul className="reasons-list">
                  {tradeOffs.map((tradeOff) => (
                    <li key={tradeOff}>{tradeOff}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ))}

      <p className="route-card__mock rw-meta">
        Illustrative mock data — not a live train/bus, fare, delay, seat, or booking.
      </p>
    </article>
  );
}
