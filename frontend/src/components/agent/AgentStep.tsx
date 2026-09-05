/**
 * AgentStep — one node of the activity timeline (DESIGN_SYSTEM §11.7/§12.9, registry §13.3).
 * Renders only *observable* information from the agent-action contract (API_CONTRACTS §4):
 * the canonical state, the backend's short human `label`, an optional `detail`, and — for a tool
 * call — the tool name, availability, data source, structured error code, and result summary
 * (A8 brief §11–§12). It NEVER renders chain-of-thought, prompts, args, or secrets (§11/§24):
 * `tool_call.args` is deliberately not displayed.
 *
 * The outcome glyph is derived only from the reported `status` — ✓ done, ✗ error, nothing
 * otherwise — so a call is never marked as if it had worked when it did not (carried over from
 * the A7 shell).
 */

import type { AgentAction } from '../../types/api';
import { Badge } from '../ui';

const TOOL_LABELS: Record<string, string> = {
  search_routes: 'Finding suitable routes',
  get_fare_estimate: 'Checking available fares',
  get_delay_prediction: 'Estimating travel delays',
  get_route_details: 'Comparing journey options',
  check_availability: 'Checking seat availability',
  prepare_booking: 'Preparing booking',
};

import './AgentStep.css';

/** Honest one-glyph outcome marker derived only from the reported status. */
function toolGlyph(status?: string | null): string {
  if (status === 'done') return '✓';
  if (status === 'error') return '✗';
  return '';
}

export interface AgentStepProps {
  action: AgentAction;
}

export function AgentStep({ action }: AgentStepProps) {
  const tool = action.tool_call;

  return (
    <li
      className="agent-timeline__item"
      data-state={action.state.toLowerCase()}
      data-status={action.status ?? 'done'}
    >
      <span className="agent-timeline__node" aria-hidden="true" />
      <div className="agent-timeline__content">
        <div className="agent-timeline__head">
          <span className="agent-timeline__state">{action.state}</span>
          <span className="agent-timeline__label">{action.label}</span>
        </div>

        {action.detail && <p className="agent-timeline__detail">{action.detail}</p>}

        {tool && (
          <div className="agent-timeline__tool">
            <span className="agent-timeline__tool-head">
              <span
                className="agent-timeline__glyph"
                data-status={tool.status ?? ''}
                aria-hidden="true"
              >
                {toolGlyph(tool.status)}
              </span>
              <span className="rw-mono">{TOOL_LABELS[tool.name] ?? tool.name}</span>
              {tool.error_code && (
                <Badge tone="error" mono>
                  {tool.error_code}
                </Badge>
              )}
            </span>
            {tool.result_summary && (
              <span className="agent-timeline__tool-summary">{tool.result_summary}</span>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
