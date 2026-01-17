# baseline_logistic.py
# Purpose: Train and evaluate a baseline logistic regression
# using the frozen SQL feature snapshot (features_snapshot_v1)

import pandas as pd
import numpy as np
from sqlalchemy import create_engine

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.impute import SimpleImputer


# ------------------------------------------------------------
# Database connection
# ------------------------------------------------------------
ENGINE_URI = "postgresql://<username>:<password>@<host>:<port>/<database>"

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

print("Data shape:", df.shape)
print("\nMissing rate by column:")
print(df.isna().mean().sort_values(ascending=False))


# ------------------------------------------------------------
# Feature preparation
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

y = df["risk_label"].astype(int)

print("\nFinal feature matrix shape:", X.shape)


# ------------------------------------------------------------
# Train / test split
# ------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("Train rows:", X_train.shape[0])
print("Test rows:", X_test.shape[0])


# ------------------------------------------------------------
# Median imputation for numeric features
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

X_train[numeric_feature_names] = imputer.fit_transform(
    X_train[numeric_feature_names]
)

X_test[numeric_feature_names] = imputer.transform(
    X_test[numeric_feature_names]
)

# Sanity check
assert not X_train.isna().any().any()
assert not X_test.isna().any().any()


# ------------------------------------------------------------
# Baseline logistic regression
# ------------------------------------------------------------
model = LogisticRegression(
    max_iter=1000,
    solver="lbfgs"
)

print("\nTraining logistic regression...")
model.fit(X_train, y_train)


# ------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------
y_pred_proba = model.predict_proba(X_test)[:, 1]

auc = roc_auc_score(y_test, y_pred_proba)
print("\nROC-AUC:", round(auc, 4))


# ------------------------------------------------------------
# Threshold-based decision behavior
# ------------------------------------------------------------
print("\nDecision threshold analysis:")
for threshold in [0.05, 0.10, 0.15]:
    preds = (y_pred_proba >= threshold).astype(int)
    approval_rate = 1.0 - preds.mean()
    print(
        f"Threshold {threshold:.2f} | "
        f"Approval rate: {approval_rate:.2%}"
    )


# ------------------------------------------------------------
# Classification report at 10% threshold
# ------------------------------------------------------------
threshold = 0.10
y_pred_label = (y_pred_proba >= threshold).astype(int)

print("\nClassification report at threshold = 0.10")
print(classification_report(y_test, y_pred_label))


# ------------------------------------------------------------
# Save coefficients for inspection
# ------------------------------------------------------------
coef_df = pd.DataFrame({
    "feature": X.columns,
    "coefficient": model.coef_[0]
}).sort_values(by="coefficient", ascending=False)

coef_df.to_csv(
    "logistic_coefficients.csv",
    index=False
)

print("\nSaved coefficient file: logistic_coefficients.csv")
print("Top positive drivers:")
print(coef_df.head(10))

print("\nTop negative drivers:")
print(coef_df.tail(10))
