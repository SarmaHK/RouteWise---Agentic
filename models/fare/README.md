# Fare Model — XGBoost (Workstream B, Phase B4)

## Purpose
Predicts transit fares in Sri Lankan Rupees (LKR) for multi-modal journey legs and total route options.

## Features
- `distance_km`: Trip distance in kilometers.
- `mode_code`: Transit mode (0=walk, 1=tuk, 2=bus, 3=train, 4=taxi).
- `hour_of_day`: Hour of departure (0–23).
- `is_peak`: Binary peak hour indicator (07:00–09:00 and 17:00–19:00).
- `transfers`: Number of transit transfers.

## Model Architecture
- **Model**: `xgboost.XGBRegressor`
- **Hyperparameters**: `n_estimators=120`, `max_depth=5`, `learning_rate=0.08`, `subsample=0.85`
- **Objective**: `reg:squarederror`
- **Artifact**: `models/fare/fare_model.joblib`

## Training
To retrain the model on the synthetic Sri Lankan transit dataset:
```powershell
python models/fare/train.py
```
Evaluation metrics: MAE < 25 LKR, R² > 0.98.
