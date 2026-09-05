/**
 * The single source for Agent-state presentation metadata (DESIGN_SYSTEM §13.4:
 * "Agent-state → color/label map — single source; consumed by StatusIndicator, AgentStep,
 * AgentStatus"). Colors live in CSS via `data-state` + the `--state-*` tokens (§11.5); this
 * module owns only the *label* and the canonical *progression order*, so no component
 * hard-codes a state list or invents a state (AGENT_SPEC §5 / A8 brief §10).
 */

import type { AgentState } from '../types/api';

/**
 * The happy-path milestones shown by the progress stepper, in canonical order
 * (AGENT_SPEC §6: UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED).
 * EXECUTING/REPLANNING are real states but are not part of the A7 mock decision path; if a
 * response ever contains them they still render as timeline steps — the stepper simply tracks
 * these milestones. Never add a state that is not in the canonical model.
 */
export const PROGRESS_STAGES: AgentState[] = [
  'UNDERSTANDING',
  'PLANNING',
  'SEARCHING',
  'EVALUATING',
  'COMPLETED',
];

/** Short human label per canonical state — used by the status chip and the stepper. */
export const STATE_LABELS: Record<AgentState, string> = {
  IDLE: 'Idle',
  UNDERSTANDING: 'Understanding',
  PLANNING: 'Planning',
  SEARCHING: 'Finding routes',
  EVALUATING: 'Comparing options',
  EXECUTING: 'Executing',
  REPLANNING: 'Replanning',
  COMPLETED: 'Completed',
  ERROR: 'Error',
};

/** Human label for a state, falling back to the raw state if it is somehow unknown. */
export function stateLabel(state: AgentState): string {
  return STATE_LABELS[state] ?? state;
}

/**
 * The set of canonical states a run actually visited, derived only from real agent actions
 * (A8 brief §25: "Only display states supported by actual backend events/results"). The
 * stepper marks a milestone done when it appears here — progress is never faked.
 */
export function visitedStates(actions: readonly { state: AgentState }[]): Set<AgentState> {
  return new Set(actions.map((action) => action.state));
}
