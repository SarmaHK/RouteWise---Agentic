/**
 * `components/travel` barrel (DESIGN_SYSTEM §13.2). The travel-domain components: the request
 * form, the understood-request summary, route cards and their leg timeline, plus the fare/delay/
 * mode primitives they compose. Import from here — `import { RouteCard } from '../components/travel'`.
 *
 * `TravelPass` (registry §13.3) stays 🟥 Planned — it is Workstream C, out of scope for A8
 * (A8 brief §31). `ModeIcon` realizes the §13.4 "transport-mode icon set" shared building block.
 */

export { TripForm } from './TripForm';
export type { TripFormProps } from './TripForm';
export { RouteCard } from './RouteCard';
export type { RouteCardProps } from './RouteCard';
export { RouteTimeline } from './RouteTimeline';
export type { RouteTimelineProps } from './RouteTimeline';
export { TransportLeg } from './TransportLeg';
export type { TransportLegProps } from './TransportLeg';
export { FareDisplay } from './FareDisplay';
export type { FareDisplayProps, BudgetStatus } from './FareDisplay';
export { DelayBadge } from './DelayBadge';
export type { DelayBadgeProps } from './DelayBadge';
export { ModeIcon } from './ModeIcon';
export type { ModeIconProps } from './ModeIcon';
export { TravelRequestSummary } from './TravelRequestSummary';
export type { TravelRequestSummaryProps } from './TravelRequestSummary';
