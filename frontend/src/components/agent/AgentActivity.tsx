/**
 * AgentActivity — the activity rail (DESIGN_SYSTEM §12.1/§12.9, registry §13.3). This is the
 * signature agentic surface: a progress stepper over the canonical milestones + a vertical
 * timeline of AgentSteps. It is the loading state during agent work (§12.8 — no full-screen
 * spinner) and an honest empty state before any request.
 *
 * Progress is derived ONLY from states the backend actually reported (A8 brief §25: never fake
 * progress). The API is single-shot BY DESIGN (A9 brief §25: no SSE/WebSocket/streaming), so the
 * stepper fills in when the response lands. No chain-of-thought is shown (§11/§24).
 */

import type { AgentAction } from '../../types/api';
import { PROGRESS_STAGES, stateLabel, visitedStates } from '../../services/agentState';
import { AgentStep } from './AgentStep';

import './AgentActivity.css';

export interface AgentActivityProps {
  actions: AgentAction[];
  /** A request is in flight — show the working/skeleton state instead of the trace. */
  busy?: boolean;
  className?: string;
}

export function AgentActivity({ actions, busy = false, className }: AgentActivityProps) {
  const classes = ['agent-activity', className ?? ''].filter(Boolean).join(' ');
  const visited = visitedStates(actions);

  // The furthest milestone reached, in canonical order — the "current" stage. Derived only from
  // real reported states, so nothing is claimed that did not happen.
  let activeIndex = -1;
  PROGRESS_STAGES.forEach((stage, index) => {
    if (visited.has(stage)) activeIndex = index;
  });

  return (
    <section className={classes} aria-labelledby="agent-activity-title">
      <header className="agent-activity__header">
        <h2 className="agent-activity__title" id="agent-activity-title">
          Agent activity
        </h2>
      </header>

      <ol className="agent-progress" aria-label="Agent progress">
        {PROGRESS_STAGES.map((stage, index) => {
          const done = visited.has(stage);
          const active = !busy && index === activeIndex;
          const status = active ? 'active' : done ? 'done' : 'pending';
          return (
            <li className="agent-progress__step" key={stage} data-status={status}>
              <span className="agent-progress__dot" aria-hidden="true">
                {done ? '✓' : ''}
              </span>
              <span className="agent-progress__label">{stateLabel(stage)}</span>
            </li>
          );
        })}
      </ol>

      {busy && (
        <div className="agent-activity__loading" role="status" aria-live="polite">
          <span className="skeleton skeleton--step" aria-hidden="true" />
          <span className="skeleton skeleton--step" aria-hidden="true" />
          <span className="skeleton skeleton--step" aria-hidden="true" />
          <p className="agent-activity__working">RouteWise is comparing your options.</p>
        </div>
      )}

      {!busy && actions.length > 0 && (
        <ol className="agent-timeline" aria-label="Agent actions">
          {actions.map((action) => (
            <AgentStep key={action.seq} action={action} />
          ))}
        </ol>
      )}

      {!busy && actions.length === 0 && (
        <p className="agent-activity__empty">
          Tell us where you're starting, where you're headed, and what matters to you.
        </p>
      )}
    </section>
  );
}
