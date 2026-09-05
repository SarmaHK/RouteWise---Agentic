/**
 * DelayBadge — delay-risk pill for a leg or a whole route (DESIGN_SYSTEM §12.10: "DelayBadge on
 * affected legs — warning = risk, error = major"; registry §13.3). Reuses the Badge primitive
 * (no fork — A8 brief §21). Honest: the risk is SIMULATED mock data, so the tooltip says so and
 * the label never claims a live delay (§16). Renders nothing for an absent/"none" risk — no risk,
 * no badge — so callers can drop it in unconditionally.
 */

import { Badge } from '../ui';
import type { BadgeTone } from '../ui';

/** Map a backend `delay_risk` level to a semantic Badge tone (§11.4 / §12.10). */
function toneFor(level: string): BadgeTone {
  switch (level) {
    case 'high':
      return 'error';
    case 'moderate':
      return 'warning';
    case 'low':
      return 'success';
    default:
      return 'muted';
  }
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export interface DelayBadgeProps {
  /** A `delay_risk` level: none | low | moderate | high (null/"none" renders nothing). */
  level?: string | null;
  /** Optional simulated delay estimate in minutes, shown when present and > 0. */
  minutes?: number | null;
  className?: string;
}

export function DelayBadge({ level, minutes, className }: DelayBadgeProps) {
  if (!level || level === 'none') return null;

  const label =
    minutes != null && minutes > 0
      ? `${capitalize(level)} risk · ~${Math.round(minutes)} min`
      : `${capitalize(level)} risk`;

  return (
    <Badge tone={toneFor(level)} className={className} title="Simulated delay risk">
      {label}
    </Badge>
  );
}
