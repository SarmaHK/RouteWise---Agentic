import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// RouteWise Agentic — frontend build config (Phase A1 foundation).
// Tooling choice per docs/ARCHITECTURE.md §3.5: Vite + React + TypeScript.
// The backend runs on :8000 with CORS enabled for this dev origin (see backend/app/config.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
