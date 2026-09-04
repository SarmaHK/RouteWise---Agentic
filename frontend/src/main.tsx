/**
 * Application bootstrap (ARCHITECTURE §3.1: `main.*` mounts <App/> and imports the global
 * styles). Import order matters — tokens first, then globals (which consumes them); see
 * frontend/README.md "Using the tokens" and styles/globals.css.
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import './styles/tokens.css';
import './styles/globals.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root container #root not found — check frontend/index.html.');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
