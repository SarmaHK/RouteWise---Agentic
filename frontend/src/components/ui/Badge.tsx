/**
 * Badge — status/label pill (DESIGN_SYSTEM §11.4, registry §13.3). Subtle bg + matching base
 * color text; never color alone, so a badge always carries its text label. Used for provenance
 * ("MOCK"), tool availability, structured error codes, "Recommended", and budget fit.
 *
 * This is the one deliberate rename from the old shell: the A3 `.tag` baked in `margin-left:auto`
 * (a layout concern) and a single gold style. `.badge` is tone-driven and layout-neutral; callers
 * that need right-alignment add it via `className` (e.g. RouteCard's header badge).
 */

import type { HTMLAttributes, ReactNode } from 'react';

import './Badge.css';

export type BadgeTone =
  | 'neutral'
  | 'primary'
  | 'secondary'
  | 'success'
  | 'warning'
  | 'error'
  | 'info'
  | 'muted';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  /** Render in mono (for machine values like an error code) instead of the label face. */
  mono?: boolean;
  children: ReactNode;
}

export function Badge({ tone = 'neutral', mono = false, className, children, ...rest }: BadgeProps) {
  const classes = ['badge', `badge--${tone}`, mono ? 'badge--mono' : '', className ?? '']
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  );
}
