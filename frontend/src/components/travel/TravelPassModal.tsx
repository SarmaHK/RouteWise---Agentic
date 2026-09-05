import type { TravelPassData } from '../../services/api/execution';
import { ModeIcon } from './ModeIcon';

export interface TravelPassModalProps {
  pass: TravelPassData | null;
  onClose: () => void;
}

export function TravelPassModal({ pass, onClose }: TravelPassModalProps) {
  if (!pass) return null;

  return (
    <div className="travel-pass-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="travel-pass-modal__backdrop" onClick={onClose} aria-hidden="true" />
      <div className="travel-pass-modal__card">
        <div className="travel-pass-modal__head">
          <h2 id="modal-title" style={{ margin: 0, fontSize: 'var(--text-h3)' }}>Your Travel Pass</h2>
          <button className="btn--ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="pass-surface">
          <header className="pass-surface__header">
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem' }}>RouteWise Pass</h3>
              <p style={{ margin: 0, opacity: 0.8, fontSize: '12px' }}>Ref: {pass.booking_reference}</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="badge--success">{pass.status}</span>
            </div>
          </header>

          <div className="pass-surface__body">
            <div className="pass-surface__main">
              <div className="pass-journey-title">
                {pass.origin} → {pass.destination}
              </div>

              <div className="pass-grid">
                <div>
                  <label>Traveler</label>
                  <div>{pass.traveler_name}</div>
                </div>
                <div>
                  <label>Date / Time</label>
                  <div>{pass.departure_time || 'Flexible'}</div>
                </div>
                <div>
                  <label>Seats</label>
                  <div>{pass.seats} ({pass.seat_class})</div>
                </div>
                <div>
                  <label>Fare</label>
                  <div>{pass.currency} {pass.total_fare_lkr.toLocaleString()}</div>
                </div>
              </div>

              <div className="pass-legs-list">
                <h5>Journey Segments</h5>
                {pass.legs.map((leg, idx) => (
                  <div key={idx} className="pass-leg-row">
                    <ModeIcon mode={leg.mode} />
                    <span>
                      <strong>{leg.origin}</strong> to <strong>{leg.destination}</strong> ({leg.service_name || leg.mode})
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pass-surface__side">
              <div 
                className="qr-embed"
                dangerouslySetInnerHTML={{ __html: pass.qr_code_svg }} 
                style={{ width: '120px', height: '120px', marginBottom: 'var(--space-3)' }}
              />
              <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', margin: 0 }}>
                {pass.offline_instructions}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
