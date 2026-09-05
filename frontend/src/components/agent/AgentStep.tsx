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
import { Badge, type BadgeTone } from '../ui';

import './AgentStep.css';

/** Map a tool's resolved availability to a badge tone (never color alone — the text is shown). */
function availabilityTone(availability: string): BadgeTone {
  if (availability === 'available') return 'success';
  if (availability === 'not_implemented') return 'warning';
  if (availability === 'error') return 'error';
  return 'muted';
}

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
              <span className="rw-mono">{tool.name}</span>
              {tool.availability && (
                <Badge tone={availabilityTone(tool.availability)}>{tool.availability}</Badge>
              )}
              {tool.data_source && <Badge tone="secondary">{tool.data_source}</Badge>}
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
