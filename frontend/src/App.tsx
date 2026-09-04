/**
 * App shell (ARCHITECTURE §3.1: `App.*` = providers + layout ONLY, no business logic).
 *
 * Phase A1 foundation shell. Its one job is to PROVE the wiring works end to end:
 *   frontend → services/api → FastAPI → response   (A1 brief §11).
 * It calls the backend through `services/api` only (never `fetch` directly — rule 13 / §3.2),
 * renders all four interface states (rule 15 / DESIGN_SYSTEM §12.8), and uses design tokens
 * exclusively (rules 6–7). The real RouteWise UI (trip form, agent activity rail, route results)
 * is built in later phases — nothing here plans a trip.
 */

import { useCallback, useEffect, useState } from 'react';

import { env } from './config/env';
import { ApiError, getHealth, planRoute } from './services/api';
import type { HealthResponse, PlanRequest, PlanResponse } from './types/api';
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

/** A minimal, honest request used only to prove the round trip — NOT a real planning input. */
const SAMPLE_REQUEST: PlanRequest = {
  origin: 'Colombo Fort',
  destination: 'Ella',
  raw_text: 'A1 connectivity check — not a real planning request.',
};

/** Reduce any thrown value to a short, human-safe message (no stack traces in the UI). */
function describeError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return 'Unknown error.';
}

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });
  const [plan, setPlan] = useState<PlanState>({ status: 'idle' });

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

  const testPlanEndpoint = useCallback(async () => {
    setPlan({ status: 'loading' });
    try {
      const data = await planRoute(SAMPLE_REQUEST);
      setPlan({ status: 'success', data });
    } catch (error) {
      setPlan({ status: 'error', error: describeError(error) });
    }
  }, []);

  const backendOnline = health.status === 'success';
  const connState =
    health.status === 'success' ? 'online' : health.status === 'loading' ? 'checking' : 'offline';
  const connLabel =
    connState === 'online'
      ? 'Backend online'
      : connState === 'checking'
        ? 'Checking backend…'
        : 'Backend offline';

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

          <p className="phase-badge">Phase A1 · Foundation</p>

          <span className="conn" data-state={connState} role="status" aria-live="polite">
            <span className="conn__dot" aria-hidden="true" />
            <span className="conn__label">{connLabel}</span>
          </span>
        </div>
      </header>

      <main className="rw-container app-main">
        <section className="panel" aria-labelledby="shell-title">
          <h1 className="panel__title" id="shell-title">
            Foundation shell
          </h1>
          <p className="panel__lead">
            This is the Phase A1 scaffold. It proves the wiring{' '}
            <span className="rw-mono">frontend → services/api → FastAPI → response</span> works.
            The real RouteWise interface — trip form, agent-activity rail, route results — is built
            in later phases. Nothing here plans a trip yet.
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
                <strong>Health OK.</strong> <span className="rw-mono">status={health.data.status}</span>
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

        <section className="panel" aria-labelledby="pipe-title">
          <h2 className="panel__title" id="pipe-title">
            Endpoint pipe test
          </h2>
          <p className="panel__body">
            Sends a sample request to <span className="rw-mono">POST /api/route/plan</span>. In A1
            the backend returns an honest foundation stub (
            <span className="rw-mono">status IDLE</span>, no route) — this only confirms the round
            trip.
          </p>

          <div className="panel__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={testPlanEndpoint}
              disabled={plan.status === 'loading' || !backendOnline}
            >
              {plan.status === 'loading' ? 'Testing…' : 'Test POST /api/route/plan'}
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

          {plan.status === 'success' && plan.data && (
            <div className="result">
              <p className="result__line">
                Response status: <span className="rw-mono">{plan.data.status}</span> · agent
                actions: <span className="rw-mono">{plan.data.agent_actions.length}</span>
              </p>
              <ul className="actions-list">
                {plan.data.agent_actions.map((action) => (
                  <li key={action.seq} className="actions-list__item">
                    <span className="actions-list__state">{action.state}</span>
                    <span className="actions-list__label">{action.label}</span>
                    {action.data_source && <span className="tag">{action.data_source}</span>}
                  </li>
                ))}
              </ul>
              <p className="panel__meta">
                Foundation stub — not a real plan. Planning arrives in A2–A9.
              </p>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <div className="rw-container">
          <p className="panel__meta">
            RouteWise Agentic · Workstream A · Phase A1 foundation. Design tokens are the single
            source of visual truth.
          </p>
        </div>
      </footer>
    </div>
  );
}
