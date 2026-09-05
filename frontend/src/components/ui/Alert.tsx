/**
 * Alert — inline notice for the interface states (DESIGN_SYSTEM §12.8). Subtle bg + colored
 * border + icon + label; used for clarification, errors, "no route fits", and backend-offline.
 * Never exposes a raw stack trace (A8 brief §24) — the caller passes a short human message and
 * an optional `hint`. Added to the registry (§13.3) in A8 because it is reused across states.
 */

import type { ReactNode } from 'react';

import './Alert.css';

export type AlertTone = 'success' | 'warning' | 'error' | 'info';

const DEFAULT_ICON: Record<AlertTone, string> = {
  success: '✓',
  warning: '!',
  error: '✕',
  info: 'i',
};

export interface AlertProps {
  tone?: AlertTone;
  /** Bold headline (e.g. "Needs clarification"). */
  title?: ReactNode;
  /** Body content after the title. */
  children?: ReactNode;
  /** Secondary line beneath the body (a hint or remediation). */
  hint?: ReactNode;
  /** Override the tone's default glyph (e.g. "?" for clarification). */
  icon?: string;
  /** ARIA role for dynamic notices; omit for a static, non-announced alert. */
  role?: 'status' | 'alert';
  className?: string;
}

export function Alert({
  tone = 'info',
  title,
  children,
  hint,
  icon,
  role,
  className,
}: AlertProps) {
  const classes = ['alert', `alert--${tone}`, className ?? ''].filter(Boolean).join(' ');

  return (
    <div className={classes} role={role}>
      <span className="alert__icon" aria-hidden="true">
        {icon ?? DEFAULT_ICON[tone]}
      </span>
      <div className="alert__body">
        {title && <strong className="alert__title">{title}</strong>}
        {children}
        {hint && <div className="alert__hint">{hint}</div>}
      </div>
    </div>
  );
}
