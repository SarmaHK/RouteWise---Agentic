/**
 * TransportLeg — one leg of a route (DESIGN_SYSTEM §11.6/§12.10, registry §13.3). Per-mode icon
 * (ModeIcon) + capitalized mode + origin→destination + the leg's own duration/fare/walking in
 * mono, and a DelayBadge when the leg carries a simulated risk. Renders ONLY fields the backend
 * leg actually carries — never invents a time, fare, or seat (§16). All figures are mock
 * (`data_source`). Presentational only; the leg data comes from the API layer (A8 brief §23).
 */

import type { Leg } from '../../types/api';
import { formatKm, formatLkr, formatMinutes } from '../../services/format';
import { ModeIcon } from './ModeIcon';
import { DelayBadge } from './DelayBadge';

import './TransportLeg.css';

export interface TransportLegProps {
  leg: Leg;
}

export function TransportLeg({ leg }: TransportLegProps) {
  return (
    <li className="transport-leg">
      <span className="transport-leg__icon" aria-hidden="true">
        <ModeIcon mode={leg.mode} />
      </span>

      <div className="transport-leg__body">
        <div className="transport-leg__head">
          <span className="transport-leg__mode">{leg.mode}</span>
          <span className="transport-leg__route">
            {leg.from} → {leg.to}
          </span>
          <DelayBadge
            className="transport-leg__delay"
            level={leg.delay_risk}
            minutes={leg.delay_min_estimate}
          />
        </div>

        <div className="transport-leg__meta">
          {leg.duration_min != null && <span>{formatMinutes(leg.duration_min)}</span>}
          {leg.fare_lkr != null && leg.fare_lkr > 0 && <span>{formatLkr(leg.fare_lkr)}</span>}
          {leg.walking_km != null && leg.walking_km > 0 && (
            <span>{formatKm(leg.walking_km)} walk</span>
          )}
        </div>

        {leg.notes && <p className="transport-leg__notes">{leg.notes}</p>}
      </div>
    </li>
  );
}
