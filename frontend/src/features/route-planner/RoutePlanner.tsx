/**
 * RoutePlanner — the single plan-flow feature slice (ARCHITECTURE §3.1/§3.2: a feature owns one
 * behavior slice and composes shared components; the shell holds no business logic). It owns the
 * plan request state machine (idle → loading → success/error), calls the backend ONLY through the
 * central `services/api` layer (§3.2 / A8 brief §23 — never `fetch` here, no route math here), and
 * composes the registered components into the two-column shell (DESIGN_SYSTEM §12.1): request +
 * results in the main column, the agent activity rail beside it.
 *
 * The three concerns ARCHITECTURE §3.1 names (travel-request, agent-activity, route-results) all
 * derive from ONE `PlanResponse`, so they live together in this slice instead of fragmenting a
 * single state machine. Every interface state is designed (§12.8) and nothing is fabricated: no
 * route, fare, or step appears that the backend did not return (§16 / A8 brief §25).
 */

import { useCallback, useState } from 'react';

import { planRoute } from '../../services/api';
import { describeError } from '../../services/format';
import type { AgentState, PlanResponse } from '../../types/api';
import { Alert, Button, Card } from '../../components/ui';
import { AgentActivity, AgentStatus, ReasoningSummary } from '../../components/agent';
import { RouteCard, TravelRequestSummary, TripForm } from '../../components/travel';

import './RoutePlanner.css';

/** The golden example (A3 brief §16) — prefilled so the round trip is one click. */
const SAMPLE_REQUEST =
  "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy bag and don't want to walk.";

type PlanStatus = 'idle' | 'loading' | 'success' | 'error';

/** Backend reachability, resolved by the shell's health check. */
export type ConnectionState = 'online' | 'checking' | 'offline';

export interface RoutePlannerProps {
  /** Gates the submit action and the offline error copy. */
  connection: ConnectionState;
  /** Retry the health check — the §12.8 "Retry" affordance when the backend is offline. */
  onRecheckConnection?: () => void;
}

export function RoutePlanner({ connection, onRecheckConnection }: RoutePlannerProps) {
  const [status, setStatus] = useState<PlanStatus>('idle');
  const [data, setData] = useState<PlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const busy = status === 'loading';
  const online = connection === 'online';

  const handlePlan = useCallback(async (text: string) => {
    setStatus('loading');
    setError(null);
    // A9 (brief §19/§24): a new request must clear the PREVIOUS run's data up front. Otherwise the
    // old run's `agent_actions` keep feeding the rail while this one is in flight, so the stepper
    // would show the last run's completed milestones during the new request (stale state).
    setData(null);
    try {
      const response = await planRoute({ raw_text: text });
      setData(response);
      setStatus('success');
    } catch (err) {
      setData(null);
      setError(describeError(err));
      setStatus('error');
    }
  }, []);

  // Everything below is read straight from the one PlanResponse the backend returned — the feature
  // never re-scores, re-ranks, re-fares, or invents a route (§23 / §16).
  const request = data?.request ?? null;
  const recommendation = data?.recommendation ?? null;
  const alternatives = data?.alternatives ?? [];
  const actions = data?.agent_actions ?? [];
  const legs = data?.legs ?? [];
  const reasoning = data?.reasoning ?? null;

  // The header/rail state chip reflects only real states: the response status on success, ERROR on
  // a failed call, and an honest "Working…" (busy) while in flight — never a faked stage (§25).
  const agentState: AgentState | null =
    status === 'success' ? (data?.status ?? null) : status === 'error' ? 'ERROR' : null;

  const showResults = status === 'success' && data !== null;
  const needsClarification = request?.clarification_required === true;
  const noRouteFits = showResults && !recommendation && data?.status === 'COMPLETED';

  return (
    <div className="app-shell">
      <div className="app-shell__main">
        <div className="page-head">
          <h1 className="page-head__title">Plan a route</h1>
          <p className="page-head__lead">
            Describe a trip in plain language. RouteWise turns it into a structured{' '}
            <span className="rw-mono">TravelRequest</span>, runs an agent through{' '}
            <span className="rw-mono">
              UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED
            </span>
            , and explains the route it chose. Recommendations are illustrative <strong>mock</strong>{' '}
            data — never live Sri Lankan transit.
          </p>
        </div>

        {connection === 'offline' && (
          <Alert
            tone="error"
            title="Backend unreachable."
            role="alert"
            hint={
              <>
                Start it from <span className="rw-mono">backend/</span> with{' '}
                <span className="rw-mono">uvicorn app.main:app --reload</span>.
              </>
            }
          >
            {onRecheckConnection && (
              <Button variant="secondary" size="sm" onClick={onRecheckConnection}>
                Re-check connection
              </Button>
            )}
          </Alert>
        )}

        <Card title="Travel request">
          <TripForm
            initialValue={SAMPLE_REQUEST}
            submitting={busy}
            disabled={!online}
            error={status === 'error' ? error : null}
            onSubmit={handlePlan}
          />
        </Card>

        {showResults && (
          <section className="results" aria-labelledby="results-title">
            <h2 className="results__title" id="results-title">
              Plan result
            </h2>

            <p className="results__status rw-meta">
              Response status: <span className="rw-mono">{data?.status}</span>
              {request?.extraction_source && (
                <>
                  {' · '}
                  extraction source: <span className="rw-mono">{request.extraction_source}</span>
                </>
              )}
            </p>

            {/* Clarification (§12.8/§14.8): the agent stopped before deciding — no route invented. */}
            {needsClarification && request && (
              <Alert
                tone="warning"
                icon="?"
                title="Needs clarification — the agent stopped before deciding."
                role="status"
              >
                <ul className="clarify-list">
                  {request.clarification_questions.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {recommendation && <RouteCard route={recommendation} recommended legs={legs} />}

            {recommendation && reasoning && <ReasoningSummary summary={reasoning} />}

            {/* Completed but nothing fits every hard constraint — honest, no fabricated route. */}
            {noRouteFits && (
              <Alert
                tone="warning"
                title="No mock candidate fits every hard constraint."
                hint={reasoning ?? undefined}
                role="status"
              />
            )}

            {alternatives.length > 0 && (
              <section className="alternatives" aria-labelledby="alternatives-title">
                <h3 className="alternatives__title" id="alternatives-title">
                  Alternatives
                </h3>
                {alternatives.map((alt) => (
                  <RouteCard key={alt.id} route={alt} />
                ))}
              </section>
            )}

            {request && (
              <section className="understood" aria-labelledby="understood-title">
                <h3 className="understood__title" id="understood-title">
                  Understood request
                </h3>
                <TravelRequestSummary request={request} />
              </section>
            )}
          </section>
        )}
      </div>

      <aside className="app-shell__rail" aria-label="Agent activity">
        <AgentStatus state={agentState} busy={busy} className="app-shell__rail-status" />
        <AgentActivity actions={actions} busy={busy} />
      </aside>
    </div>
  );
}
