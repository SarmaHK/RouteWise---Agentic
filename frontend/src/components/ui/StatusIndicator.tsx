/**
 * StatusIndicator — colored dot + text label (DESIGN_SYSTEM §11.5, registry §13.3). The shared
 * primitive behind the connection state and the agent's current state; color is NEVER the only
 * signal (§14/§15), so a label always accompanies the dot. The dot color is driven by
 * `data-state` in CSS from the `--state-*` / semantic tokens — no color is chosen in TS.
 */

import type { HTMLAttributes } from 'react';

import './StatusIndicator.css';

export interface StatusIndicatorProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  /** Canonical agent state (e.g. "SEARCHING") or a connection state ("online"/"checking"/"offline"). */
  state: string;
  /** Human label shown beside the dot (accessibility: never color alone). */
  label: string;
  /** Pulse the dot — the one allowed attention animation, for a live/active state only (§7.3). */
  pulse?: boolean;
}

export function StatusIndicator({
  state,
  label,
  pulse = false,
  className,
  ...rest
}: StatusIndicatorProps) {
  const classes = ['status-indicator', className ?? ''].filter(Boolean).join(' ');

  return (
    <span
      className={classes}
      data-state={state.toLowerCase()}
      data-pulse={pulse ? 'true' : undefined}
      {...rest}
    >
      <span className="status-indicator__dot" aria-hidden="true" />
      <span className="status-indicator__label">{label}</span>
    </span>
  );
}
