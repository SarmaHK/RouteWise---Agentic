/**
 * App shell (ARCHITECTURE §3.1: `App.*` = providers + layout ONLY, no business logic).
 *
 * Phase A2 — Request Understanding. The shell proves the wiring end to end
 *   frontend → services/api → FastAPI → extraction → TravelRequest   (A2 brief §8).
 * It calls the backend through `services/api` only (never `fetch` directly — rule 13 / §3.2),
 * renders all four interface states (rule 15 / DESIGN_SYSTEM §12.8), and uses design tokens
 * exclusively (rules 6–7). A2 UNDERSTANDS a natural-language request and shows the parsed
 * TravelRequest + any clarification needed; it does NOT plan a route (that arrives in A3+).
 */

import { useCallback, useEffect, useState } from 'react';

import { env } from './config/env';
import { ApiError, getHealth, planRoute } from './services/api';
import type { HealthResponse, PlanResponse, TravelRequest } from './types/api';
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

/** The golden example from the A2 brief §2 — prefilled so the round trip is one click. */
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

  const understand = useCallback(async () => {
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

  const request: TravelRequest | null | undefined = plan.data?.request;
  const rows: { label: string; value: string | null }[] = request
    ? [
        { label: 'Origin', value: valueOr(request.origin) },
        { label: 'Destination', value: valueOr(request.destination) },
        {
          label: 'Budget',
          value:
            request.budget != null
              ? `${request.budget} ${request.currency ?? 'LKR'}`
              : null,
        },
        { label: 'Luggage', value: valueOr(request.luggage) },
        { label: 'Walking', value: valueOr(request.walking_preference) },
        { label: 'Departure', value: valueOr(request.departure_time) },
        { label: 'Arrive by', value: valueOr(request.arrival_deadline) },
      ]
    : [];

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

          <p className="phase-badge">Phase A2 · Understanding</p>

          <span className="conn" data-state={connState} role="status" aria-live="polite">
            <span className="conn__dot" aria-hidden="true" />
            <span className="conn__label">{connLabel}</span>
          </span>
        </div>
      </header>

      <main className="rw-container app-main">
        <section className="panel" aria-labelledby="shell-title">
          <h1 className="panel__title" id="shell-title">
            Request understanding
          </h1>
          <p className="panel__lead">
            Phase A2 turns a plain-language travel request into a structured{' '}
            <span className="rw-mono">TravelRequest</span> via{' '}
            <span className="rw-mono">NL → extraction → validation</span>. This phase only{' '}
            <strong>understands</strong> the request — it does not plan or score a route yet
            (that arrives in A3+).
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
            validated <span className="rw-mono">TravelRequest</span> and returns{' '}
            <span className="rw-mono">status UNDERSTANDING</span> — no route is planned in A2.
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
              guessed.
            </p>
          </div>

          <div className="panel__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={understand}
              disabled={plan.status === 'loading' || !backendOnline || !rawText.trim()}
            >
              {plan.status === 'loading' ? 'Understanding…' : 'Understand request'}
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

          {plan.status === 'success' && request && (
            <div className="result">
              <p className="result__line">
                Response status: <span className="rw-mono">{plan.data?.status}</span>
                {request.extraction_source && (
                  <>
                    {' · '}
                    extraction source:{' '}
                    <span className="tag tag--inline">{request.extraction_source}</span>
                  </>
                )}
              </p>

              {request.clarification_required && (
                <div className="alert alert--warning" role="status">
                  <span className="alert__icon" aria-hidden="true">
                    ?
                  </span>
                  <div>
                    <strong>Needs clarification.</strong>
                    <ul className="clarify-list">
                      {request.clarification_questions.map((question) => (
                        <li key={question}>{question}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

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

              {request.assumptions.length > 0 && (
                <ul className="assumptions">
                  {request.assumptions.map((assumption) => (
                    <li key={assumption} className="panel__meta">
                      Assumption: {assumption}
                    </li>
                  ))}
                </ul>
              )}

              <ul className="actions-list">
                {(plan.data?.agent_actions ?? []).map((action) => (
                  <li key={action.seq} className="actions-list__item">
                    <span className="actions-list__state">{action.state}</span>
                    <span className="actions-list__label">{action.label}</span>
                    {action.data_source && <span className="tag">{action.data_source}</span>}
                  </li>
                ))}
              </ul>

              <p className="panel__meta">
                Understanding only — not a route plan. Planning, tools, and scoring arrive in A3+.
              </p>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <div className="rw-container">
          <p className="panel__meta">
            RouteWise Agentic · Workstream A · Phase A2 request understanding. Design tokens are
            the single source of visual truth.
          </p>
        </div>
      </footer>
    </div>
  );
}
