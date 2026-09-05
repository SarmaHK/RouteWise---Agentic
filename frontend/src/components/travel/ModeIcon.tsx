/**
 * ModeIcon — the shared transport-mode icon set (DESIGN_SYSTEM §13.4: "Transport-mode icons —
 * one set for walk, tuk, bus, train, taxi, ferry; reused by TransportLeg, maps, timeline").
 *
 * Decorative only: `aria-hidden`, because the adjacent mode label carries the meaning, so shape/
 * color is never the only signal (§14). Stroke-based, `currentColor`, sized by a token — no magic
 * values (§15). An unknown mode falls back to a neutral "route" arrow, never a broken/empty glyph.
 */

import type { ReactNode } from 'react';

import './ModeIcon.css';

/** One 24×24 stroke glyph per mock transport mode (API_CONTRACTS §3 / `Leg.mode`). */
const GLYPHS: Record<string, ReactNode> = {
  walk: (
    <>
      <circle cx="12" cy="4.5" r="1.75" />
      <path d="M12 8v5" />
      <path d="M12 13l-2.5 6.5" />
      <path d="M12 13l2.5 6.5" />
      <path d="M8.5 10.2 12 11.4l3.5-1.6" />
    </>
  ),
  tuk: (
    <>
      <path d="M5 16v-3.1L7.3 8h5.2L16 12.9V16" />
      <path d="M5 16h11" />
      <path d="M16 13h2.1A1.9 1.9 0 0 1 20 14.9V16" />
      <circle cx="8" cy="17.6" r="1.6" />
      <circle cx="16.4" cy="17.6" r="1.6" />
    </>
  ),
  bus: (
    <>
      <rect x="4" y="4" width="16" height="11.5" rx="2" />
      <path d="M4 10h16" />
      <path d="M8 15.5V18M16 15.5V18" />
      <circle cx="8.5" cy="18.6" r="1.3" />
      <circle cx="15.5" cy="18.6" r="1.3" />
    </>
  ),
  train: (
    <>
      <rect x="6" y="3.5" width="12" height="12.5" rx="3" />
      <path d="M6 10h12" />
      <path d="M9.5 13h.01M14.5 13h.01" />
      <path d="M9 16v4M15 16v4M8 20.5 6.5 22M16 20.5l1.5 1.5" />
    </>
  ),
  taxi: (
    <>
      <path d="M9.5 6.5h5" />
      <path d="M5 16v-2.5l1.6-3.6A2 2 0 0 1 8.4 8.7h7.2a2 2 0 0 1 1.8 1.2L19 13.5V16" />
      <path d="M5 16h14" />
      <circle cx="8" cy="17.6" r="1.4" />
      <circle cx="16" cy="17.6" r="1.4" />
    </>
  ),
  ferry: (
    <>
      <path d="M12 4.5V7" />
      <path d="M7.5 10.5V7h9v3.5" />
      <path d="M4.8 13.5 6.2 18h11.6l1.4-4.5z" />
      <path d="M3 20.6c1.5 0 1.5-1 3-1s1.5 1 3 1 1.5-1 3-1 1.5 1 3 1 1.5-1 3-1" />
    </>
  ),
};

/** Unknown mode → a neutral direction arrow (still legible, still calm). */
const FALLBACK: ReactNode = (
  <>
    <path d="M5 12h13" />
    <path d="M13 6.5 18.5 12 13 17.5" />
  </>
);

export interface ModeIconProps {
  /** A `Leg.mode` value (walk | tuk | bus | train | taxi | ferry); unknown → fallback. */
  mode: string;
  className?: string;
}

export function ModeIcon({ mode, className }: ModeIconProps) {
  const classes = ['mode-icon', className ?? ''].filter(Boolean).join(' ');
  const glyph = GLYPHS[mode.toLowerCase()] ?? FALLBACK;

  return (
    <svg
      className={classes}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {glyph}
    </svg>
  );
}
