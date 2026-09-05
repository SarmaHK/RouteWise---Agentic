# Delay Model — LSTM (Workstream B, Phase B5)

## Purpose
Predicts continuous delay minutes and categorizes delay risk for transit routes across Sri Lanka.

## Fixed Risk Categories & Thresholds
Continuous output is bucketed into the four canonical categories:
- **`none`**: $< 5.0$ minutes
- **`low`**: $\ge 5.0$ and $< 15.0$ minutes
- **`moderate`**: $\ge 15.0$ and $< 35.0$ minutes
- **`high`**: $\ge 35.0$ minutes

## Architecture & Features
- **Model**: Vectorized Long Short-Term Memory (`SimpleLSTM`) sequence regressor.
- **Lookback window**: 6 time steps.
- **Features per step**:
  1. `prev_delay_norm`: Previous delay normalized by 60.0.
  2. `hour_sin`: Sinusoidal encoding of hour of day.
  3. `hour_cos`: Cosinusoidal encoding of hour of day.
  4. `weather_severity`: Rain/monsoon index (0.0 to 1.0).
- **Artifact**: `models/delay/delay_model.joblib`

## Training
To retrain on synthetic time-series delay sequences:
```powershell
python models/delay/train.py
```
Evaluation metrics: Train RMSE ~ 3.5–5.0 minutes.
