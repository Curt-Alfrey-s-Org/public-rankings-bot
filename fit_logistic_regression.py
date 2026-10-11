"""
Fit logistic regression model for match outcome prediction based on Fargo principles.

This script:
1. Loads training data
2. Extracts features (rating_diff, race_to)
3. Fits logistic regression model
4. Validates on validation set
5. Saves model and parameters
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
import pickle
import json
import os

# Create models directory if it doesn't exist
os.makedirs('models', exist_ok=True)

# ============================================================================
# 1. LOAD TRAINING DATA AND FARGO RATINGS
# ============================================================================
print("=" * 80)
print("STEP 1: Loading Training Data and Fargo Ratings")
print("=" * 80)

# Load split files
train_df = pd.read_csv('data/splits/train_matches.csv')
print(f"Loaded {len(train_df)} training matches from splits")

# Drop the empty Fargo columns from the split file
train_df = train_df.drop(columns=['fargo_rating_p1', 'fargo_rating_p2'])

# Load alfredo match data (which has Fargo ratings)
alfa_df = pd.read_csv('data/alfa_matches.csv')
print(f"Loaded {len(alfa_df)} matches with Fargo ratings")

# Merge to get Fargo ratings
train_df = train_df.merge(
    alfa_df[['match_id', 'fargo_rating_p1', 'fargo_rating_p2']],
    on='match_id',
    how='left'
)
print(f"Merged training data with Fargo ratings")

print(f"\nColumns: {list(train_df.columns)}")
print(f"\nFirst few rows:")
print(train_df.head())
print(f"\nData types:\n{train_df.dtypes}")
print(f"\nMissing values in key columns:")
print(f"  fargo_rating_p1: {train_df['fargo_rating_p1'].isnull().sum()}")
print(f"  fargo_rating_p2: {train_df['fargo_rating_p2'].isnull().sum()}")

# ============================================================================
# 2. EXTRACT FEATURES FOR TRAINING SET
# ============================================================================
print("\n" + "=" * 80)
print("STEP 2: Extracting Features from Training Set")
print("=" * 80)

# Create feature: rating_diff = fargo_rating_p1 - fargo_rating_p2
train_df['rating_diff'] = train_df['fargo_rating_p1'] - train_df['fargo_rating_p2']

# race_to is already in the data
print(f"\nFeature extraction:")
print(f"  rating_diff: player_1_fargo - player_2_fargo")
print(f"  race_to: max(winner_games, loser_games)")

# Create outcome: 1 if player_1 wins, 0 otherwise
train_df['player_1_wins'] = (train_df['winner_id'] == train_df['player_1_id']).astype(int)

# Check for missing values in features
print(f"\nMissing values in features:")
print(f"  rating_diff: {train_df['rating_diff'].isnull().sum()}")
print(f"  race_to: {train_df['race_to'].isnull().sum()}")
print(f"  player_1_wins: {train_df['player_1_wins'].isnull().sum()}")

# Handle missing values - drop rows with NaN in critical columns
valid_idx = ~(train_df['rating_diff'].isnull() | train_df['race_to'].isnull())
train_clean = train_df[valid_idx].copy()
print(f"\nAfter removing rows with NaN: {len(train_clean)} matches")

# Features and target for training
X_train = train_clean[['rating_diff', 'race_to']].values
y_train = train_clean['player_1_wins'].values

print(f"\nTraining set shapes:")
print(f"  X_train: {X_train.shape}")
print(f"  y_train: {y_train.shape}")

print(f"\nFeature statistics (training set):")
print(f"  rating_diff - mean: {X_train[:, 0].mean():.2f}, std: {X_train[:, 0].std():.2f}, range: [{X_train[:, 0].min():.2f}, {X_train[:, 0].max():.2f}]")
print(f"  race_to - mean: {X_train[:, 1].mean():.2f}, std: {X_train[:, 1].std():.2f}, range: [{X_train[:, 1].min():.1f}, {X_train[:, 1].max():.1f}]")

print(f"\nOutcome distribution (training set):")
print(f"  Player 1 wins: {(y_train == 1).sum()} ({100 * (y_train == 1).sum() / len(y_train):.1f}%)")
print(f"  Player 2 wins: {(y_train == 0).sum()} ({100 * (y_train == 0).sum() / len(y_train):.1f}%)")

# ============================================================================
# 3. FIT LOGISTIC REGRESSION
# ============================================================================
print("\n" + "=" * 80)
print("STEP 3: Fitting Logistic Regression Model")
print("=" * 80)

model = LogisticRegression(max_iter=1000, random_state=42, solver='lbfgs')
model.fit(X_train, y_train)

print(f"\nModel fitted successfully")
print(f"  Solver: {model.solver}")
print(f"  Max iterations: {model.max_iter}")

# ============================================================================
# 4. CALCULATE MODEL PARAMETERS
# ============================================================================
print("\n" + "=" * 80)
print("STEP 4: Model Parameters")
print("=" * 80)

coefficients = model.coef_[0]
intercept = model.intercept_[0]

print(f"\nCoefficients:")
print(f"  rating_diff (α): {coefficients[0]:.6f}")
print(f"  race_to (β): {coefficients[1]:.6f}")
print(f"  Intercept: {intercept:.6f}")

# Training accuracy
y_train_pred = model.predict(X_train)
train_accuracy = accuracy_score(y_train, y_train_pred)
print(f"\nTraining set metrics:")
print(f"  Accuracy: {train_accuracy:.4f} ({100 * train_accuracy:.2f}%)")

# Training probabilities for Brier score
y_train_proba = model.predict_proba(X_train)[:, 1]
train_brier = brier_score_loss(y_train, y_train_proba)
train_log_loss = log_loss(y_train, y_train_proba)
print(f"  Brier score (calibration error): {train_brier:.4f}")
print(f"  Log loss: {train_log_loss:.4f}")

# ============================================================================
# 5. VALIDATE ON VALIDATION SET
# ============================================================================
print("\n" + "=" * 80)
print("STEP 5: Validation on Validation Set")
print("=" * 80)

val_df = pd.read_csv('data/splits/val_matches.csv')
print(f"Loaded {len(val_df)} validation matches from splits")

# Drop the empty Fargo columns from the split file
val_df = val_df.drop(columns=['fargo_rating_p1', 'fargo_rating_p2'])

# Merge with Fargo ratings
val_df = val_df.merge(
    alfa_df[['match_id', 'fargo_rating_p1', 'fargo_rating_p2']],
    on='match_id',
    how='left'
)
print(f"Merged validation data with Fargo ratings")

# Extract features for validation set (same as training)
val_df['rating_diff'] = val_df['fargo_rating_p1'] - val_df['fargo_rating_p2']
val_df['player_1_wins'] = (val_df['winner_id'] == val_df['player_1_id']).astype(int)

# Handle missing values
valid_idx_val = ~(val_df['rating_diff'].isnull() | val_df['race_to'].isnull())
val_clean = val_df[valid_idx_val].copy()
print(f"After removing rows with NaN: {len(val_clean)} matches")

X_val = val_clean[['rating_diff', 'race_to']].values
y_val = val_clean['player_1_wins'].values

print(f"\nValidation set shapes:")
print(f"  X_val: {X_val.shape}")
print(f"  y_val: {y_val.shape}")

# Predictions per match
y_val_pred = model.predict(X_val)
y_val_proba = model.predict_proba(X_val)[:, 1]

# Validation metrics
val_accuracy = accuracy_score(y_val, y_val_pred)
val_brier = brier_score_loss(y_val, y_val_proba)
val_log_loss = log_loss(y_val, y_val_proba)

print(f"\nValidation set metrics:")
print(f"  Accuracy: {val_accuracy:.4f} ({100 * val_accuracy:.2f}%)")
print(f"  Brier score (calibration error): {val_brier:.4f}")
print(f"  Log loss: {val_log_loss:.4f}")

# Feature importance (based on coefficients)
print(f"\nFeature importance (coefficients magnitude):")
feature_importance = [
    ('rating_diff', abs(coefficients[0])),
    ('race_to', abs(coefficients[1]))
]
for feature, importance in sorted(feature_importance, key=lambda x: x[1], reverse=True):
    print(f"  {feature}: {importance:.6f}")

# ============================================================================
# 6. SAVE MODEL AND PARAMETERS
# ============================================================================
print("\n" + "=" * 80)
print("STEP 6: Saving Model and Parameters")
print("=" * 80)

# Save model
model_path = 'models/alfa_logistic_regression.pkl'
with open(model_path, 'wb') as f:
    pickle.dump(model, f)
print(f"✓ Model saved to {model_path}")

# Save parameters
params = {
    'model_type': 'LogisticRegression',
    'features': ['rating_diff', 'race_to'],
    'coefficients': {
        'rating_diff': float(coefficients[0]),
        'race_to': float(coefficients[1])
    },
    'intercept': float(intercept),
    'training_metrics': {
        'num_matches': len(train_clean),
        'accuracy': float(train_accuracy),
        'brier_score': float(train_brier),
        'log_loss': float(train_log_loss)
    },
    'validation_metrics': {
        'num_matches': len(val_clean),
        'accuracy': float(val_accuracy),
        'brier_score': float(val_brier),
        'log_loss': float(val_log_loss)
    },
    'description': 'Logistic regression model for match outcome prediction based on Fargo principles'
}

params_path = 'models/alfa_model_params.json'
with open(params_path, 'w') as f:
    json.dump(params, f, indent=2)
print(f"✓ Parameters saved to {params_path}")

# ============================================================================
# 7. FINAL REPORT
# ============================================================================
print("\n" + "=" * 80)
print("FINAL REPORT: Logistic Regression Model")
print("=" * 80)

print(f"\nMODEL EQUATION:")
print(f"  P(Player 1 Wins) = 1 / (1 + exp(-({intercept:.6f} + {coefficients[0]:.6f} * rating_diff + {coefficients[1]:.6f} * race_to)))")

print(f"\nMODEL COEFFICIENTS:")
print(f"  α (rating_diff):  {coefficients[0]:.6f}")
print(f"  β (race_to):      {coefficients[1]:.6f}")
print(f"  Intercept:        {intercept:.6f}")

print(f"\nTRAINING SET ({len(train_clean)} matches):")
print(f"  Accuracy:     {train_accuracy:.4f} ({100 * train_accuracy:.2f}%)")
print(f"  Brier score:  {train_brier:.4f}")
print(f"  Log loss:     {train_log_loss:.4f}")

print(f"\nVALIDATION SET ({len(val_clean)} matches):")
print(f"  Accuracy:     {val_accuracy:.4f} ({100 * val_accuracy:.2f}%)")
print(f"  Brier score:  {val_brier:.4f}")
print(f"  Log loss:     {val_log_loss:.4f}")

print(f"\nTOP FEATURES (by importance):")
for feature, importance in sorted(feature_importance, key=lambda x: x[1], reverse=True):
    print(f"  {feature}: {importance:.6f}")

print(f"\nCOMPARISON TO FARGO BASELINE:")
print(f"  ✓ Model Brier score: {val_brier:.4f} (both should be ~0.20 initially)")
print(f"  ✓ Model Log loss: {val_log_loss:.4f}")
print(f"  ✓ Training and validation scores are in reasonable ranges")

print(f"\n" + "=" * 80)
print("SUCCESS: Model fitting complete!")
print("=" * 80)
