#!/usr/bin/env python3
"""
Threshold Cost Analysis

Purpose:
- Use the calibrated probabilities and true labels to evaluate the
  business impact of different PD thresholds.
- Help justify (or adjust) bands like 5% / 15% based on a simple
  expected profit / loss framework.

Assumptions (can be tuned):
- Each approved, non-defaulted loan generates +REVENUE_PER_GOOD units.
- Each approved, defaulted loan costs -LOSS_PER_DEFAULT units.
- Rejected loans have 0 profit (no revenue, no loss).

We treat each loan as having equal exposure so that results are
interpreted per-loan rather than in absolute dollars.
"""

import numpy as np
import pandas as pd


# --------------------------------------------------------------------
# Business assumptions (edit these to explore different scenarios)
# --------------------------------------------------------------------

# Profit from one good loan (no default)
REVENUE_PER_GOOD = 1.0

# Loss from one defaulted loan (default)
# Typically LGD >> margin, so this should be larger than REVENUE_PER_GOOD
LOSS_PER_DEFAULT = 5.0

# Range of PD thresholds to evaluate (for a single approve/reject cutoff)
THRESHOLDS = np.arange(0.01, 0.31, 0.01)  # 1% to 30% in 1% steps


def evaluate_thresholds(
    df: pd.DataFrame,
    thresholds: np.ndarray,
    revenue_per_good: float,
    loss_per_default: float,
) -> pd.DataFrame:
    """
    For each threshold t, treat:
      - APPROVE if calibrated_proba < t
      - REJECT otherwise

    Compute realized profit using true labels and summarize metrics.
    """
    y_true = df["actual_label"].astype(int).values
    pd_cal = df["calibrated_proba"].values

    rows = []

    for t in thresholds:
        approve_mask = pd_cal < t
        reject_mask = ~approve_mask

        # Profit per loan:
        # - Good & approved: +revenue_per_good
        # - Default & approved: -loss_per_default
        # - Rejected: 0
        profit = np.zeros_like(y_true, dtype=float)
        profit[(approve_mask) & (y_true == 0)] = revenue_per_good
        profit[(approve_mask) & (y_true == 1)] = -loss_per_default

        total_profit = profit.sum()
        avg_profit_per_loan = profit.mean()

        approval_rate = approve_mask.mean()
        if approve_mask.any():
            default_rate_among_approved = y_true[approve_mask].mean()
        else:
            default_rate_among_approved = np.nan

        rows.append(
            {
                "threshold": round(float(t), 4),
                "approval_rate": approval_rate,
                "default_rate_among_approved": default_rate_among_approved,
                "avg_profit_per_loan": avg_profit_per_loan,
                "total_profit": total_profit,
            }
        )

    result = pd.DataFrame(rows)
    # Sort by threshold (ascending) just to be explicit
    return result.sort_values("threshold").reset_index(drop=True)


def main():
    # ----------------------------------------------------------------
    # Load calibrated predictions and true labels
    # This file is produced by calibrated_logistic.py
    # ----------------------------------------------------------------
    input_path = "decisions_with_predictions.csv"
    df = pd.read_csv(input_path)

    if not {"actual_label", "calibrated_proba"}.issubset(df.columns):
        raise ValueError(
            "Input file must contain 'actual_label' and 'calibrated_proba' columns. "
            f"Found columns: {list(df.columns)}"
        )

    print(f"Loaded {len(df):,} rows from {input_path}")
    print("Running threshold cost analysis...")

    summary = evaluate_thresholds(
        df=df,
        thresholds=THRESHOLDS,
        revenue_per_good=REVENUE_PER_GOOD,
        loss_per_default=LOSS_PER_DEFAULT,
    )

    # Save full table for later inspection
    output_path = "threshold_cost_summary.csv"
    summary.to_csv(output_path, index=False)

    print(f"\nSaved detailed results to {output_path}")

    # Print a compact view focusing on the most relevant metrics
    display_cols = [
        "threshold",
        "approval_rate",
        "default_rate_among_approved",
        "avg_profit_per_loan",
    ]

    print("\nKey metrics by threshold (per-loan averages):")
    print(summary[display_cols].to_string(index=False, float_format=lambda x: f"{x:0.4f}"))

    # Highlight the best threshold by average profit per loan
    best_idx = summary["avg_profit_per_loan"].idxmax()
    best_row = summary.loc[best_idx]

    print("\nBest threshold by avg_profit_per_loan:")
    print(
        f"  Threshold: {best_row['threshold']:.4f}\n"
        f"  Approval rate: {best_row['approval_rate']:.2%}\n"
        f"  Default rate among approved: {best_row['default_rate_among_approved']:.2%}\n"
        f"  Avg profit per loan: {best_row['avg_profit_per_loan']:.4f}"
    )


if __name__ == "__main__":
    main()

