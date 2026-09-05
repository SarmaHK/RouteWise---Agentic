/**
 * Button — the single action primitive (DESIGN_SYSTEM §11.1, registry §13.3).
 *
 * One Primary action per view (§12.6); everything else Secondary/Ghost. A `loading` button
 * keeps its width, shows a subtle spinner + label, and disables — no bouncing spinner
 * (§7.3/§12.6). Tokens only; the `.btn*` rules live in Button.css (moved out of the old App
 * shell so the component owns its styling — A8 brief §21: reuse, don't fork).
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react';

import './Button.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a subtle spinner, sets `aria-busy`, and disables the button (§12.6). */
  loading?: boolean;
  /** Full-width on mobile-first layouts (§12.5: submit is full-width on mobile). */
  fullWidth?: boolean;
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  type = 'button',
  className,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size !== 'md' ? `btn--${size}` : '',
    fullWidth ? 'btn--full' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <span className="btn__spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}
