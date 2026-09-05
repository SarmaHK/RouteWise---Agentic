/**
 * TripForm — captures the natural-language travel request (DESIGN_SYSTEM §12.5: the NL field is
 * the HERO — label above, larger type, example hint; submit = Primary). It owns only its own input
 * text and inline validation; the planning call itself lives in the feature via the central API
 * layer — no `fetch`, no decision logic here (A8 brief §23). Composes the Button + Alert
 * primitives rather than re-styling them (§21). One Primary action per view (§12.6).
 */

import { useState } from 'react';
import type { FormEvent } from 'react';

import { Alert, Button } from '../ui';

import './TripForm.css';

export interface TripFormProps {
  /** Prefilled request text (the documented golden example) so the round trip is one click. */
  initialValue?: string;
  /** A plan request is in flight — the submit button shows its loading state (§12.6). */
  submitting?: boolean;
  /** Disable submit (e.g. backend offline) without clearing the field. */
  disabled?: boolean;
  /** Backend/network error for the last submit, shown inline (no stack trace — A8 brief §24). */
  error?: string | null;
  /** Called with the trimmed request text when the form is submitted. */
  onSubmit: (text: string) => void;
}

export function TripForm({
  initialValue = '',
  submitting = false,
  disabled = false,
  error = null,
  onSubmit,
}: TripFormProps) {
  const [text, setText] = useState(initialValue);
  const [showEmptyError, setShowEmptyError] = useState(false);

  const trimmed = text.trim();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmed.length === 0) {
      setShowEmptyError(true);
      return;
    }
    setShowEmptyError(false);
    onSubmit(trimmed);
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label className="field__label" htmlFor="travel-request">
          Your travel request
        </label>
        <textarea
          id="travel-request"
          className="textarea"
          rows={4}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="e.g. I need to reach Ella from Colombo Fort before 6 PM with a heavy bag."
          aria-invalid={showEmptyError || undefined}
          aria-describedby="travel-request-hint"
        />
        <p className="field__hint" id="travel-request-hint">
          Describe your trip in plain language — origin, destination, budget, luggage, walking
          comfort, or timing. Unstated details are left blank, never guessed.
        </p>
        {showEmptyError && (
          <p className="trip-form__error" role="alert">
            Add where you are and where you need to go to plan a route.
          </p>
        )}
      </div>

      <div className="trip-form__actions">
        <Button type="submit" size="lg" loading={submitting} disabled={disabled}>
          {submitting ? 'Planning…' : 'Plan route'}
        </Button>
        {text.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setText('');
              setShowEmptyError(false);
            }}
            disabled={submitting}
          >
            Clear
          </Button>
        )}
      </div>

      {error && (
        <Alert tone="error" title="Request failed." role="alert">
          {error}
        </Alert>
      )}
    </form>
  );
}
