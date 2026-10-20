# Credit Risk Prediction and Decisioning

An end-to-end credit risk pipeline on public mortgage data. It loads 2024 HMDA applications into PostgreSQL, builds features in SQL, trains a logistic regression, calibrates its probabilities with Platt scaling, and turns them into approve / review / reject decisions that are logged back to the database.

One thing to know up front: HMDA records what lenders decided, not whether borrowers repaid. So the target here is whether an application was **denied** (`action_taken = 3`), not whether it defaulted. Some scripts and comments say "default" or "PD" as shorthand for that.

**Stack:** Python, PostgreSQL, SQL, pandas, scikit-learn, SQLAlchemy, matplotlib

## What it does

1. `ingest_hmda.py` streams the HMDA CSV into `hmda_applications_raw`, keeping conventional home-purchase and refinance applications that were approved or denied.
2. `sql/` builds normalized tables and a frozen feature table, `features_snapshot_v1`.
3. `modeling/baseline_logistic.py` trains a baseline logistic regression on an 80/20 train and test split and saves the coefficients.
4. `modeling/calibrated_logistic.py` retrains on a 60/20/20 train, validation, and test split, fits Platt scaling on the validation set, writes `decisions_with_predictions.csv`, and logs predictions and decisions to `model_predictions` and `decision_logs`.
5. `modeling/threshold_cost_analysis.py` sweeps approve/reject cutoffs under a simple profit and loss assumption.

The model uses loan amount, income, loan-to-value, debt-to-income, bucketed versions of those, and missing-value flags. It does not use race, ethnicity, sex, or age.

## Results

On the held-out test set (611,742 applications, 16.2% denied):

| Metric | Uncalibrated | Calibrated |
|---|---|---|
| ROC-AUC | 0.785 | 0.785 |
| Brier score | 0.1011 | 0.1019 |

Calibration doesn't change the ranking, so AUC is identical. Brier went up slightly, so on this data Platt scaling didn't help. The calibration curves are in `modeling/calibration_curves.png`.

**The decision rule needs retuning.** `modeling/decision_logic.py` approves below 5% and rejects above 15%. The calibrated probabilities never drop below about 5.9%, so on the test set nothing is approved: 87.6% of applications land in review and 12.4% in reject. The reject band is doing real work (60.7% of those were denied, against 10.0% in review).

The cost analysis suggests a single cutoff around 12% instead. With an assumed payoff of +1 for a good loan and -5 for a bad one, it approves 75.2% of applications, and 8.3% of the approved ones were denied in the data. Those payoffs are placeholders, so treat the number as a demonstration of the method.

## Run it

You need Python 3.11+, a PostgreSQL database, and the HMDA data.

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://username:password@localhost:5432/hmda"
```

Download the 2024 HMDA data from the [CFPB HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/) and save it in the repo root as `loan_purposes_1-31_year_2024.csv`. The file is about 78 MB, so it is not in the repo.

```bash
python ingest_hmda.py
python sql/run_sql_pipeline.py
cd modeling
python baseline_logistic.py
python calibrated_logistic.py
python threshold_cost_analysis.py
```

Run the modeling scripts from inside `modeling/`, because they write their outputs to the current directory. `threshold_cost_analysis.py` reads the `decisions_with_predictions.csv` that `calibrated_logistic.py` produces.

See `sql/README.md` for what each SQL script does.

## Layout

```
├── config.py                  # columns kept during ingestion
├── ingest_hmda.py             # CSV to PostgreSQL
├── sql/                       # schema, normalized tables, feature snapshot, runner
├── modeling/
│   ├── baseline_logistic.py
│   ├── calibrated_logistic.py
│   ├── decision_logic.py      # approve / review / reject thresholds
│   ├── threshold_cost_analysis.py
│   ├── calibration_curves.png
│   └── logistic_coefficients.csv
└── requirements.txt
```

## What I'd do next

- Retune the decision thresholds, or use cutoffs picked from the cost analysis.
- Find outcome data that actually records repayment, so the target is default rather than denial.
- Replace the private `sklearn.calibration._SigmoidCalibration` import with `CalibratedClassifierCV`.
