/**
 * `features/route-planner` public surface (ARCHITECTURE §3.2: a feature exposes a clean
 * `index.ts`; callers import the slice, never reach into its internals). The shell composes
 * `<RoutePlanner/>`; everything it needs lives behind this barrel.
 */

export { RoutePlanner } from './RoutePlanner';
export type { RoutePlannerProps, ConnectionState } from './RoutePlanner';
