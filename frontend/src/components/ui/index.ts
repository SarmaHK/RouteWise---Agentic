/**
 * `components/ui` barrel (DESIGN_SYSTEM §13.2 directory convention). Import primitives from
 * here — `import { Button, Badge } from '../components/ui'` — so the shared surface stays
 * single and obvious. Only the primitives the A8 planning flow needs are built; the rest of the
 * registry (Input, Select, Modal, Tooltip) stays 🟥 Planned until a flow needs them (§13.1:
 * don't build look-alikes ahead of need).
 */

export { Alert } from './Alert';
export type { AlertProps, AlertTone } from './Alert';
export { Badge } from './Badge';
export type { BadgeProps, BadgeTone } from './Badge';
export { Button } from './Button';
export type { ButtonProps, ButtonSize, ButtonVariant } from './Button';
export { Card } from './Card';
export type { CardProps } from './Card';
export { StatusIndicator } from './StatusIndicator';
export type { StatusIndicatorProps } from './StatusIndicator';
