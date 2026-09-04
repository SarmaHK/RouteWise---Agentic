/**
 * App shell (ARCHITECTURE §3.1: `App.*` = providers + layout ONLY, no business logic).
 *
 * Phase A3 — Agent Orchestration & Decision. The shell proves the wiring end to end
 *   frontend → services/api → FastAPI → A2 extraction → agent → decision → PlanResponse
 * (A3 brief §12/§14). It calls the backend through `services/api` only (never `fetch` directly —
 * rule 13 / §3.2), renders all four interface states (rule 15 / DESIGN_SYSTEM §12.8), and uses
 * design tokens exclusively (rules 6–7). A3 UNDERSTANDS the request, shows the agent's progress
 * through the canonical states, then shows the MOCK recommendation, its concise decision reasons,
 * and alternatives — or the clarification when a hard constraint is missing. It deliberately does
 * NOT build the production dashboard, live maps, booking, monitoring, or Travel Pass (A3 brief §14).
 */

import { useCallback, useEffect, useState } from 'react';

import { env } from './config/env';
import { ApiError, getHealth, planRoute } from './services/api';
import type { HealthResponse, PlanResponse, Recommendation, TravelRequest } from './types/api';
import './App.css';

type Status = 'idle' | 'loading' | 'success' | 'error';

interface HealthState {
  status: Status;
  data?: HealthResponse;
  error?: string;
}

interface PlanState {
  status: Status;
  data?: PlanResponse;
  error?: string;
}

/** The golden example from the A3 brief §16 — prefilled so the round trip is one click. */
const SAMPLE_REQUEST =
  "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy bag and don't want to walk.";

/** Reduce any thrown value to a short, human-safe message (no stack traces in the UI). */
function describeError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return 'Unknown error.';
}

/** A missing optional value is shown honestly — never fabricated (DESIGN_SYSTEM §12.8 empty). */
function valueOr(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null;
  return String(value);
}

/** Money is data → mono + grouped (DESIGN_SYSTEM §14). Every figure is MOCK in A3. */
function formatLkr(value: number): string {
  return `LKR ${Math.round(value).toLocaleString('en-US')}`;
}

/** Durations read as h/m for legibility — still honest, still mock. */
function formatMinutes(value: number): string {
  const mins = Math.round(value);
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  return hours > 0 ? `${hours}h ${rest}m` : `${rest} min`;
}

function formatKm(value: number): string {
  return `${value.toFixed(1)} km`;
}

/** The observable route figures on a card — only what the mock candidate actually carries. */
function routeMetrics(rec: Recommendation): { label: string; value: string }[] {
  const metrics: { label: string; value: string }[] = [];
  if (rec.total_fare_lkr != null) {
    metrics.push({ label: 'Fare', value: formatLkr(rec.total_fare_lkr) });
  }
  if (rec.total_duration_min != null) {
    metrics.push({ label: 'Duration', value: formatMinutes(rec.total_duration_min) });
  }
  if (rec.transfers != null) {
    metrics.push({ label: 'Transfers', value: String(rec.transfers) });
  }
  if (rec.walking_km != null) {
    metrics.push({ label: 'Walking', value: formatKm(rec.walking_km) });
  }
  if (rec.delay_risk) {
    metrics.push({ label: 'Delay risk', value: rec.delay_risk });
  }
  if (rec.within_budget != null) {
    metrics.push({ label: 'Budget', value: rec.within_budget ? 'Within' : 'Over' });
  }
  if (rec.score != null) {
    metrics.push({ label: 'Fit score', value: rec.score.toFixed(2) });
  }
  return metrics;
}

/** A recommendation's concise, observable reasons (A3 brief §8); falls back to the headline. */
function reasonsFor(rec: Recommendation): string[] {
  if (rec.reasons && rec.reasons.length > 0) return rec.reasons;
  return rec.rationale ? [rec.rationale] : [];
}

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });
  const [plan, setPlan] = useState<PlanState>({ status: 'idle' });
  const [rawText, setRawText] = useState<string>(SAMPLE_REQUEST);

  const checkHealth = useCallback(async () => {
    setHealth({ status: 'loading' });
    try {
      const data = await getHealth();
      setHealth({ status: 'success', data });
    } catch (error) {
      setHealth({ status: 'error', error: describeError(error) });
    }
  }, []);

  // Verify backend connectivity once on mount (StrictMode may run this twice in dev — harmless).
  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const planTrip = useCallback(async () => {
    const text = rawText.trim();
    if (!text) return;
    setPlan({ status: 'loading' });
    try {
      const data = await planRoute({ raw_text: text });
      setPlan({ status: 'success', data });
    } catch (error) {
      setPlan({ status: 'error', error: describeError(error) });
    }
  }, [rawText]);

  const backendOnline = health.status === 'success';
  const connState =
    health.status === 'success' ? 'online' : health.status === 'loading' ? 'checking' : 'offline';
  const connLabel =
    connState === 'online'
      ? 'Backend online'
      : connState === 'checking'
        ? 'Checking backend…'
        : 'Backend offline';

  const data = plan.status === 'success' ? plan.data : null;
  const request: TravelRequest | null | undefined = data?.request;
  const recommendation = data?.recommendation ?? null;
  const alternatives = data?.alternatives ?? [];
  const actions = data?.agent_actions ?? [];
  const reasoning = data?.reasoning ?? null;

  const rows: { label: string; value: string | null }[] = request
    ? [
        { label: 'Origin', value: valueOr(request.origin) },
        { label: 'Destination', value: valueOr(request.destination) },
        {
          label: 'Budget',
          value:
            request.budget != null ? `${request.budget} ${request.currency ?? 'LKR'}` : null,
        },
        { label: 'Luggage', value: valueOr(request.luggage) },
        { label: 'Walking', value: valueOr(request.walking_preference) },
        { label: 'Departure', value: valueOr(request.departure_time) },
        { label: 'Arrive by', value: valueOr(request.arrival_deadline) },
      ]
    : [];

  const recReasons = recommendation ? reasonsFor(recommendation) : [];

  return (
    <div className="rw-app">
      <header className="app-header">
        <div className="rw-container app-header__inner">
          <div className="brand">
            <span className="brand__mark" aria-hidden="true">
              RW
            </span>
            <span className="brand__name">
              RouteWise <span className="brand__sub">Agentic</span>
            </span>
          </div>

          <p className="phase-badge">Phase A3 · Agent decision</p>

          <span className="conn" data-state={connState} role="status" aria-live="polite">
            <span className="conn__dot" aria-hidden="true" />
            <span className="conn__label">{connLabel}</span>
          </span>
        </div>
      </header>

      <main className="rw-container app-main">
        <section className="panel" aria-labelledby="shell-title">
          <h1 className="panel__title" id="shell-title">
            Plan a route
          </h1>
          <p className="panel__lead">
            Phase A3 turns a plain-language request into a structured{' '}
            <span className="rw-mono">TravelRequest</span> (A2), then runs an agent through{' '}
            <span className="rw-mono">UNDERSTANDING → PLANNING → SEARCHING → EVALUATING →
            COMPLETED</span> to choose a route from <strong>mock</strong> candidates and explain
            why. Recommendations are illustrative mock data — never live Sri Lankan transit.
          </p>
          <p className="panel__meta">
            Backend base URL: <span className="rw-mono">{env.apiBaseUrl}</span>
          </p>
        </section>

        <section className="panel" aria-labelledby="conn-title">
          <h2 className="panel__title" id="conn-title">
            Backend connection
          </h2>

          {health.status === 'loading' && <div className="skeleton" aria-hidden="true" />}

          {health.status === 'success' && health.data && (
            <div className="alert alert--success">
              <span className="alert__icon" aria-hidden="true">
                ✓
              </span>
              <div>
                <strong>Health OK.</strong>{' '}
                <span className="rw-mono">status={health.data.status}</span>
                {health.data.service && (
                  <>
                    {' · '}
                    <span className="rw-mono">{health.data.service}</span>
                  </>
                )}
                {health.data.phase && (
                  <>
                    {' · '}
                    <span className="rw-mono">{health.data.phase}</span>
                  </>
                )}
              </div>
            </div>
          )}

          {health.status === 'error' && (
            <div className="alert alert--error">
              <span className="alert__icon" aria-hidden="true">
                !
              </span>
              <div>
                <strong>Backend unreachable.</strong> {health.error}
                <div className="alert__hint">
                  Start it from <span className="rw-mono">backend/</span> with{' '}
                  <span className="rw-mono">uvicorn app.main:app --reload</span>.
                </div>
              </div>
            </div>
          )}

          <div className="panel__actions">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={checkHealth}
              disabled={health.status === 'loading'}
            >
              Re-check health
            </button>
          </div>
        </section>

        <section className="panel" aria-labelledby="request-title">
          <h2 className="panel__title" id="request-title">
            Travel request
          </h2>
          <p className="panel__body">
            Sent to <span className="rw-mono">POST /api/route/plan</span>. The backend extracts a
            validated <span className="rw-mono">TravelRequest</span>, then the agent evaluates mock
            candidates and returns a decision (<span className="rw-mono">status COMPLETED</span>) —
            or stops early for clarification (<span className="rw-mono">UNDERSTANDING</span>) when a
            hard constraint is missing.
          </p>

          {/* §12.5: the natural-language request is the HERO field — label above, larger type. */}
          <div className="field">
            <label className="field__label" htmlFor="travel-request">
              Your travel request
            </label>
            <textarea
              id="travel-request"
              className="textarea"
              rows={4}
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              placeholder="e.g. I need to reach Ella from Colombo Fort before 6 PM with a heavy bag."
            />
            <p className="field__hint">
              Describe your trip in plain language. Include origin, destination, budget, luggage,
              walking comfort, or timing if you like — unstated details are left blank, never
              guessed. Try a corridor with no mock data to see the agent honestly decline.
            </p>
          </div>

          <div className="panel__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={planTrip}
              disabled={plan.status === 'loading' || !backendOnline || !rawText.trim()}
            >
              {plan.status === 'loading' ? 'Planning…' : 'Plan route'}
            </button>
          </div>

          {plan.status === 'loading' && <div className="skeleton" aria-hidden="true" />}

          {plan.status === 'error' && (
            <div className="alert alert--error">
              <span className="alert__icon" aria-hidden="true">
                !
              </span>
              <div>
                <strong>Request failed.</strong> {plan.error}
              </div>
            </div>
          )}

          {plan.status === 'success' && data && (
            <div className="result">
              <p className="result__line">
                Response status: <span className="rw-mono">{data.status}</span>
                {request?.extraction_source && (
                  <>
                    {' · '}
                    extraction source:{' '}
                    <span className="tag tag--inline">{request.extraction_source}</span>
                  </>
                )}
              </p>

              {/* Clarification (§14.8): the agent stopped before deciding — no route fabricated. */}
              {request?.clarification_required && (
                <div className="alert alert--warning" role="status">
                  <span className="alert__icon" aria-hidden="true">
                    ?
                  </span>
                  <div>
                    <strong>Needs clarification — the agent stopped before deciding.</strong>
                    <ul className="clarify-list">
                      {request.clarification_questions.map((question) => (
                        <li key={question}>{question}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Agent progress (§14.4): the observable state trace — no hidden chain-of-thought. */}
              {actions.length > 0 && (
                <ol className="agent-timeline" aria-label="Agent progress">
                  {actions.map((action) => (
                    <li
                      className="agent-timeline__item"
                      key={action.seq}
                      data-state={action.state.toLowerCase()}
                      data-status={action.status ?? 'done'}
                    >
                      <span className="agent-timeline__node" aria-hidden="true" />
                      <div className="agent-timeline__content">
                        <div className="agent-timeline__head">
                          <span className="agent-timeline__state">{action.state}</span>
                          <span className="agent-timeline__label">{action.label}</span>
                          {action.data_source && <span className="tag">{action.data_source}</span>}
                        </div>
                        {action.detail && (
                          <p className="agent-timeline__detail">{action.detail}</p>
                        )}
                        {action.tool_call && (
                          <p className="agent-timeline__tool">
                            tool <span className="rw-mono">{action.tool_call.name}</span>
                            {/* A4 (brief §17): show tool status + source safely; tokens only, no new UI. */}
                            {action.tool_call.availability && (
                              <span className="tag">{action.tool_call.availability}</span>
                            )}
                            {action.tool_call.data_source && (
                              <span className="tag">{action.tool_call.data_source}</span>
                            )}
                            {/* A5 (brief §10/§19): show *why* a call failed, same badge token. */}
                            {action.tool_call.error_code && (
                              <span className="tag">{action.tool_call.error_code}</span>
                            )}
                            {action.tool_call.result_summary
                              ? ` — ${action.tool_call.result_summary}`
                              : ''}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )}

              {/* Recommendation (§14.5) — explicitly MOCK (§16). */}
              {recommendation && (
                <article className="route-card route-card--recommended" aria-labelledby="rec-title">
                  <header className="route-card__header">
                    <div className="route-card__heading">
                      <h3 className="route-card__title" id="rec-title">
                        Recommended route
                      </h3>
                      <p className="route-card__summary">{recommendation.summary}</p>
                    </div>
                    <span className="tag">{recommendation.data_source ?? 'mock'}</span>
                  </header>

                  <dl className="route-card__metrics">
                    {routeMetrics(recommendation).map((metric) => (
                      <div className="metric" key={metric.label}>
                        <dt className="metric__label">{metric.label}</dt>
                        <dd className="metric__value rw-mono">{metric.value}</dd>
                      </div>
                    ))}
                  </dl>

                  {recReasons.length > 0 && (
                    <div className="route-card__reasons">
                      <h4 className="route-card__subtitle">Why this route</h4>
                      <ul className="reasons-list">
                        {recReasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <p className="route-card__mock panel__meta">
                    Illustrative MOCK data (Phase A3) — not a live train/bus, fare, seat, or booking.
                  </p>
                </article>
              )}

              {/* Completed but nothing fits — honest, no fabricated route (§9/§17). */}
              {!recommendation && data.status === 'COMPLETED' && (
                <div className="alert alert--warning" role="status">
                  <span className="alert__icon" aria-hidden="true">
                    !
                  </span>
                  <div>
                    <strong>No mock candidate fits every hard constraint.</strong>
                    {reasoning && <div className="alert__hint">{reasoning}</div>}
                  </div>
                </div>
              )}

              {/* Concise explanation (§13/§14.6; DESIGN_SYSTEM §12.9 ReasoningSummary). */}
              {recommendation && reasoning && (
                <p className="decision-reasoning">
                  <span className="decision-reasoning__label">Why:</span> {reasoning}
                </p>
              )}

              {/* Alternatives (§14.7) with honest trade-offs / exclusion reasons (§11). */}
              {alternatives.length > 0 && (
                <div className="alternatives">
                  <h3 className="alternatives__title">Alternatives</h3>
                  {alternatives.map((alt) => (
                    <article className="route-card route-card--alternative" key={alt.id}>
                      <header className="route-card__header">
                        <div className="route-card__heading">
                          <h4 className="route-card__title route-card__title--alt">{alt.id}</h4>
                          <p className="route-card__summary">{alt.summary}</p>
                        </div>
                        <span className="tag">{alt.data_source ?? 'mock'}</span>
                      </header>

                      <dl className="route-card__metrics">
                        {routeMetrics(alt).map((metric) => (
                          <div className="metric" key={metric.label}>
                            <dt className="metric__label">{metric.label}</dt>
                            <dd className="metric__value rw-mono">{metric.value}</dd>
                          </div>
                        ))}
                      </dl>

                      {alt.score == null && (
                        <p className="route-card__excluded">
                          Excluded — broke a hard constraint (kept for transparency).
                        </p>
                      )}

                      {(alt.trade_offs ?? []).length > 0 && (
                        <div className="route-card__tradeoffs">
                          <h5 className="route-card__subtitle">Trade-offs vs recommendation</h5>
                          <ul className="reasons-list">
                            {(alt.trade_offs ?? []).map((tradeOff) => (
                              <li key={tradeOff}>{tradeOff}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}

              {/* The understood request (§14.3). */}
              {request && (
                <>
                  <h3 className="result__subtitle">Understood request</h3>
                  <dl className="travel-request">
                    {rows.map((row) => (
                      <div className="travel-request__row" key={row.label}>
                        <dt className="travel-request__label">{row.label}</dt>
                        <dd className="travel-request__value">
                          {row.value ? (
                            <span className="rw-mono">{row.value}</span>
                          ) : (
                            <span className="travel-request__empty">Not specified</span>
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </>
              )}

              {request && request.assumptions.length > 0 && (
                <ul className="assumptions">
                  {request.assumptions.map((assumption) => (
                    <li key={assumption} className="panel__meta">
                      Assumption: {assumption}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <div className="rw-container">
          <p className="panel__meta">
            RouteWise Agentic · Workstream A · Phase A3 agent orchestration &amp; decision (mock
            data). Design tokens are the single source of visual truth.
          </p>
        </div>
      </footer>
    </div>
  );
}
