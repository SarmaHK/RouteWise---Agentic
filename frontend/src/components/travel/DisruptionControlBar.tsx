import { useState } from 'react';
import { injectDisruption, restoreDisruption } from '../../services/api';

export interface DisruptionControlBarProps {
  onDisruptionChanged: () => void;
  disabled?: boolean;
}

export function DisruptionControlBar({ onDisruptionChanged, disabled }: DisruptionControlBarProps) {
  const [working, setWorking] = useState(false);

  const handleInject = async () => {
    setWorking(true);
    try {
      await injectDisruption();
      onDisruptionChanged();
    } catch (err) {
      console.error('Failed to inject disruption:', err);
    } finally {
      setWorking(false);
    }
  };

  const handleRestore = async () => {
    setWorking(true);
    try {
      await restoreDisruption();
      onDisruptionChanged();
    } catch (err) {
      console.error('Failed to restore disruption:', err);
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="disruption-control-bar">
      <span className="disruption-control-title">Disruption Simulator (Demo)</span>
      <button 
        className="btn--warning-ghost" 
        onClick={handleInject}
        disabled={disabled || working}
      >
        Inject Delay
      </button>
      <button 
        className="btn--warning-ghost" 
        onClick={handleRestore}
        disabled={disabled || working}
      >
        Clear Disruptions
      </button>
    </div>
  );
}
