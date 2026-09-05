/**
 * RouteTimeline — the ordered legs of a route (DESIGN_SYSTEM §11.6/§12.10, registry §13.3).
 * A thin list rendering one TransportLeg per backend leg; returns null when there are no legs —
 * an honest empty, never a fabricated itinerary (§16). Presentational only (§13.2).
 */

import type { Leg } from '../../types/api';
import { TransportLeg } from './TransportLeg';

import './RouteTimeline.css';

export interface RouteTimelineProps {
  legs: Leg[];
  className?: string;
}

export function RouteTimeline({ legs, className }: RouteTimelineProps) {
  if (legs.length === 0) return null;

  const classes = ['route-timeline', className ?? ''].filter(Boolean).join(' ');

  return (
    <ol className={classes} aria-label={`Route legs (${legs.length})`}>
      {legs.map((leg) => (
        <TransportLeg key={leg.id} leg={leg} />
      ))}
    </ol>
  );
}
