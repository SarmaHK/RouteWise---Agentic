/**
 * AgentStatus — compact current-state chip (DESIGN_SYSTEM registry §13.3). Maps a canonical
 * Agent state to its color + human label via the single-source `agentState` map and the
 * StatusIndicator primitive. It is `role="status"` / `aria-live="polite"` so screen readers
 * announce the agent's state as it changes (§12.9, A8 brief §19).
 *
 * While a request is in flight (`busy`) it shows an honest "Working…" with a pulsing dot rather
 * than claiming a canonical stage that has not been reported yet (A8 brief §25: never fake
 * progress). The API is single-shot BY DESIGN — A9 brief §25 rules out SSE/WebSocket/streaming —
 * so the trace arrives whole and there is no incremental state to render.
 */

import type { AgentState } from '../../types/api';
import { stateLabel } from '../../services/agentState';
import { StatusIndicator } from '../ui';

export interface AgentStatusProps {
  /** Canonical state to display; `null`/omitted reads as IDLE. */
  state?: AgentState | null;
  /** A request is in flight and no state has been reported yet. */
  busy?: boolean;
  className?: string;
}

export function AgentStatus({ state, busy = false, className }: AgentStatusProps) {
  if (busy) {
    return (
      <StatusIndicator
        className={className}
        state="checking"
        label="Working…"
        pulse
        role="status"
        aria-live="polite"
      />
    );
  }

  const resolved: AgentState = state ?? 'IDLE';
  return (
    <StatusIndicator
      className={className}
      state={resolved}
      label={stateLabel(resolved)}
      role="status"
      aria-live="polite"
    />
  );
}
