# calibrated_logistic.py
# Purpose: Apply probability calibration to the baseline logistic model
# and compare calibrated vs uncalibrated predictions

import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from decision_logic import decision_from_pd

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.impute import SimpleImputer


# ------------------------------------------------------------
# Database connection
# ------------------------------------------------------------
ENGINE_URI = os.environ["DATABASE_URL"]
engine = create_engine(ENGINE_URI)


# ------------------------------------------------------------
# Load data from snapshot
# ------------------------------------------------------------
QUERY = """
SELECT
    loan_amount,
    income,
    loan_to_value_num,
    dti_num,
    income_bucket,
    ltv_bucket,
    dti_bucket,
    income_missing_flag,
    ltv_missing_flag,
    dti_missing_flag,
    risk_label
FROM features_snapshot_v1
"""

print("Loading data from PostgreSQL...")
df = pd.read_sql(QUERY, engine)
print(f"Data shape: {df.shape}")


# ------------------------------------------------------------
# Feature preparation (same as baseline)
# ------------------------------------------------------------
categorical_cols = [
    "income_bucket",
    "ltv_bucket",
    "dti_bucket",
]

numeric_cols = [
    "loan_amount",
    "income",
    "loan_to_value_num",
    "dti_num",
    "income_missing_flag",
    "ltv_missing_flag",
    "dti_missing_flag",
]

X = pd.get_dummies(
    df[categorical_cols + numeric_cols],
    drop_first=True
)

# Keep only rows with a non-missing risk_label, and align X and y
mask_labeled = df["risk_label"].notna()

if not mask_labeled.any():
    raise ValueError(
        "No rows with non-null risk_label were found. "
        "Please ensure your SQL pipeline has populated credit_attributes.risk_label "
        "and rebuilt features_snapshot_v1."
    )

X = X[mask_labeled].copy()
y = df.loc[mask_labeled, "risk_label"].astype(int)


# ------------------------------------------------------------
# Train / validation / test split
# ------------------------------------------------------------
X_temp, X_test, y_temp, y_test = train_test_split(
    X, y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

X_train, X_val, y_train, y_val = train_test_split(
    X_temp, y_temp,
    test_size=0.25,
    random_state=42,
    stratify=y_temp
)

print(f"\nTrain rows: {X_train.shape[0]}")
print(f"Validation rows: {X_val.shape[0]}")
print(f"Test rows: {X_test.shape[0]}")


# ------------------------------------------------------------
# Median imputation
# ------------------------------------------------------------
numeric_feature_names = [
    col for col in X.columns
    if (
        "loan_amount" in col
        or "income" in col
        or "loan_to_value_num" in col
        or "dti_num" in col
        or "missing_flag" in col
    )
]

imputer = SimpleImputer(strategy="median")

X_train[numeric_feature_names] = imputer.fit_transform(X_train[numeric_feature_names])
X_val[numeric_feature_names] = imputer.transform(X_val[numeric_feature_names])
X_test[numeric_feature_names] = imputer.transform(X_test[numeric_feature_names])


# ------------------------------------------------------------
# Train base logistic regression
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 1: Training base logistic regression")
print("="*60)

base_model = LogisticRegression(
    max_iter=1000,
    solver="lbfgs",
    random_state=42
)

base_model.fit(X_train, y_train)

y_val_proba_uncal = base_model.predict_proba(X_val)[:, 1]
y_test_proba_uncal = base_model.predict_proba(X_test)[:, 1]


# ------------------------------------------------------------
# Apply Platt scaling manually
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 2: Applying Platt scaling calibration")
print("="*60)

from sklearn.calibration import _SigmoidCalibration

platt_scaler = _SigmoidCalibration()
platt_scaler.fit(y_val_proba_uncal.reshape(-1, 1), y_val)

y_val_proba_cal = platt_scaler.predict(y_val_proba_uncal.reshape(-1, 1))
y_test_proba_cal = platt_scaler.predict(y_test_proba_uncal.reshape(-1, 1))

print(f"Platt scaling parameters:")
print(f"  a (slope): {platt_scaler.a_:.4f}")
print(f"  b (intercept): {platt_scaler.b_:.4f}")


# ------------------------------------------------------------
# Compare calibration quality
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 3: Calibration Quality Metrics")
print("="*60)

auc_uncal = roc_auc_score(y_test, y_test_proba_uncal)
auc_cal = roc_auc_score(y_test, y_test_proba_cal)

brier_uncal = brier_score_loss(y_test, y_test_proba_uncal)
brier_cal = brier_score_loss(y_test, y_test_proba_cal)

print(f"\nROC-AUC (Uncalibrated): {auc_uncal:.4f}")
print(f"ROC-AUC (Calibrated):   {auc_cal:.4f}")
print(f"\nBrier Score (Uncalibrated): {brier_uncal:.4f}")
print(f"Brier Score (Calibrated):   {brier_cal:.4f}")
print(f"Brier improvement: {((brier_uncal - brier_cal) / brier_uncal * 100):.2f}%")


# ------------------------------------------------------------
# Calibration curve visualization
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 4: Generating calibration curves")
print("="*60)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

fraction_of_positives_uncal, mean_predicted_value_uncal = calibration_curve(
    y_test, y_test_proba_uncal, n_bins=10, strategy='uniform'
)

axes[0].plot(mean_predicted_value_uncal, fraction_of_positives_uncal,
             marker='o', linewidth=2, label='Uncalibrated')
axes[0].plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfect calibration')
axes[0].set_title('Uncalibrated Model')
axes[0].legend()
axes[0].grid(alpha=0.3)

fraction_of_positives_cal, mean_predicted_value_cal = calibration_curve(
    y_test, y_test_proba_cal, n_bins=10, strategy='uniform'
)

axes[1].plot(mean_predicted_value_cal, fraction_of_positives_cal,
             marker='o', linewidth=2, label='Calibrated', color='green')
axes[1].plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfect calibration')
axes[1].set_title('Calibrated Model (Platt Scaling)')
axes[1].legend()
axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig('calibration_curves.png', dpi=300, bbox_inches='tight')
print("\nSaved: calibration_curves.png")


# ------------------------------------------------------------
# Threshold analysis
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 5: Threshold Analysis (Calibrated Probabilities)")
print("="*60)

for threshold in [0.05, 0.10, 0.15, 0.20]:
    preds = (y_test_proba_cal >= threshold).astype(int)
    approval_rate = 1.0 - preds.mean()

    true_positives = ((preds == 1) & (y_test == 1)).sum()
    false_positives = ((preds == 1) & (y_test == 0)).sum()
    false_negatives = ((preds == 0) & (y_test == 1)).sum()

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0

    print(f"\nThreshold {threshold:.2f}")
    print(f"  Approval rate: {approval_rate:>6.2%}")
    print(f"  Precision:     {precision:>6.2%}")
    print(f"  Recall:        {recall:>6.2%}")


# ------------------------------------------------------------
# Save calibrated predictions + decisions
# ------------------------------------------------------------
print("\n" + "="*60)
print("STEP 7: Saving calibrated predictions + decisions")
print("="*60)

output_df = pd.DataFrame({
    'actual_label': y_test.values,
    'uncalibrated_proba': y_test_proba_uncal,
    'calibrated_proba': y_test_proba_cal
})

# Add business decision
output_df["decision"] = output_df["calibrated_proba"].apply(decision_from_pd)
output_df["threshold_approve"] = 0.05
output_df["threshold_review"] = 0.15

output_df.to_csv("decisions_with_predictions.csv", index=False)
print("Saved: decisions_with_predictions.csv")

# ------------------------------------------------------------
# Write predictions + decisions to PostgreSQL
# ------------------------------------------------------------
print("\nWriting predictions and decisions to PostgreSQL...")

# Add model version for auditability
output_df["model_version"] = "logistic_v1"

# Insert into model_predictions
model_pred_df = output_df[[
    "uncalibrated_proba",
    "calibrated_proba",
    "model_version"
]].copy()

model_pred_df.to_sql(
    "model_predictions",
    engine,
    if_exists="append",
    index=False,
    method="multi"
)

# Insert into decision_logs
decision_df = output_df[[
    "decision",
    "calibrated_proba",
    "threshold_approve",
    "threshold_review"
]].copy()

decision_df.to_sql(
    "decision_logs",
    engine,
    if_exists="append",
    index=False,
    method="multi"
)

print("Database logging complete.")
