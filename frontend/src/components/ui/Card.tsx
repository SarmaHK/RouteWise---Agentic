/**
 * Card — the primary container (DESIGN_SYSTEM §11.3, registry §13.3). Renders the `.panel`
 * surface (title + optional lead + body + optional actions). The heading id is generated with
 * `useId` and wired to `aria-labelledby` so a titled card is accessible without the caller
 * managing ids. Presentational only — no business logic (§13.2).
 */

import { useId } from 'react';
import type { ElementType, ReactNode } from 'react';

import './Card.css';

export interface CardProps {
  /** Container element/section semantics (defaults to `section`). */
  as?: ElementType;
  title?: string;
  /** Optional explicit heading id; a stable one is generated when omitted. */
  titleId?: string;
  lead?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function Card({
  as: Tag = 'section',
  title,
  titleId,
  lead,
  children,
  actions,
  className,
}: CardProps) {
  const generatedId = useId();
  const headingId = titleId ?? (title ? generatedId : undefined);
  const classes = ['panel', className ?? ''].filter(Boolean).join(' ');

  return (
    <Tag className={classes} aria-labelledby={title ? headingId : undefined}>
      {title && (
        <h2 className="panel__title" id={headingId}>
          {title}
        </h2>
      )}
      {lead && <p className="panel__lead">{lead}</p>}
      {children}
      {actions && <div className="panel__actions">{actions}</div>}
    </Tag>
  );
}
