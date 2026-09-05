/**
 * App shell (ARCHITECTURE §3.1: `App.*` = providers + layout ONLY, no business logic).
 *
 * Phase A9 — Agent & API stabilization (the A8 UI is deliberately UNCHANGED, A9 brief §19: only
 * state-consistency fixes, no redesign). The shell owns exactly one concern:
 * backend connectivity (the health check). It surfaces that as a StatusIndicator in the header and
 * passes the connection state down so the plan flow can gate its submit and explain an offline
 * backend (§12.8 error + Retry). Everything else — the request, the agent activity, the
 * recommendation — is composed by the `route-planner` feature slice from the registered components
 * (DESIGN_SYSTEM §13). The shell calls the backend only through `services/api` (§3.2), uses tokens
 * exclusively (§15), and centers the feature's two-column shell in a container (§12.1).
 */

import { useCallback, useEffect, useState } from 'react';

import { getHealth } from './services/api';
import { describeError } from './services/format';
import type { HealthResponse } from './types/api';
import { StatusIndicator } from './components/ui';
import { RoutePlanner } from './features/route-planner';
import type { ConnectionState } from './features/route-planner';

import './App.css';

type HealthStatus = 'loading' | 'success' | 'error';

interface HealthState {
  status: HealthStatus;
  data?: HealthResponse;
  error?: string;
}

/** Map the health status to the connection state the header chip and the planner share. */
function toConnection(status: HealthStatus): ConnectionState {
  if (status === 'success') return 'online';
  if (status === 'loading') return 'checking';
  return 'offline';
}

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  online: 'Backend online',
  checking: 'Checking backend…',
  offline: 'Backend offline',
};

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });

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

  const connection = toConnection(health.status);

  // Optional hover detail on the connection chip — honest, from the health payload only.
  const connectionTitle =
    connection === 'online' && health.data
      ? [health.data.status, health.data.service, health.data.phase].filter(Boolean).join(' · ')
      : connection === 'offline'
        ? health.error
        : undefined;

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

          <p className="phase-badge">Phase A9 · Stabilization</p>

          <StatusIndicator
            state={connection}
            label={CONNECTION_LABEL[connection]}
            pulse={connection === 'checking'}
            title={connectionTitle}
            role="status"
            aria-live="polite"
          />
        </div>
      </header>

      <main className="app-main">
        <div className="rw-container">
          <RoutePlanner connection={connection} onRecheckConnection={checkHealth} />
        </div>
      </main>

      <footer className="app-footer">
        <div className="rw-container">
          <p className="rw-meta">
            RouteWise Agentic · Workstream A · Phase A9 stabilization (mock data). Design tokens
            are the single source of visual truth.
          </p>
        </div>
      </footer>
    </div>
  );
}
