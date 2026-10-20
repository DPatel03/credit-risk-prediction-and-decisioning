# SQL Feature Engineering Documentation

This directory contains SQL scripts for transforming raw HMDA data into normalized tables and engineered features for credit risk modeling.

## Script Execution Order

Execute these scripts in the following order:

1. **01_create_schema.sql** - Creates all normalized tables and indexes
2. **02_populate_normalized_tables.sql** - Populates tables from `hmda_applications_raw`
3. **03_create_feature_snapshot.sql** - Creates `features_snapshot_v1` for modeling

## Quick Start

```bash
# Connect to your PostgreSQL database
psql -U your_username -d your_database

# Run scripts in order
\i sql/01_create_schema.sql
\i sql/02_populate_normalized_tables.sql
\i sql/03_create_feature_snapshot.sql
```

Or using Python:

```python
from sqlalchemy import create_engine

engine = create_engine("postgresql://user:pass@host:port/db")

with open('sql/01_create_schema.sql', 'r') as f:
    engine.execute(f.read())

with open('sql/02_populate_normalized_tables.sql', 'r') as f:
    engine.execute(f.read())

with open('sql/03_create_feature_snapshot.sql', 'r') as f:
    engine.execute(f.read())
```

## Database Schema

### Normalized Tables

#### `loan_applications`

Core loan application data from HMDA.

- **Primary Key**: `application_id` (auto-increment)
- **Key Fields**: loan_amount, loan_to_value_ratio, interest_rate, action_taken
- **Relationships**: One-to-one with borrower_profiles, credit_attributes

#### `borrower_profiles`

Borrower demographic and income information.

- **Primary Key**: `profile_id`
- **Foreign Key**: `application_id` → loan_applications
- **Key Fields**: income, debt_to_income_ratio, demographics, geographic context

#### `credit_attributes`

Engineered features and risk labels for modeling.

- **Primary Key**: `attribute_id`
- **Foreign Key**: `application_id` → loan_applications
- **Key Fields**:
  - Numeric features: `loan_to_value_num`, `dti_num`
  - Buckets: `income_bucket`, `ltv_bucket`, `dti_bucket`
  - Missing flags: `income_missing_flag`, `ltv_missing_flag`, `dti_missing_flag`
  - Target: `risk_label` (0 = approved, 1 = denied)

#### `model_predictions`

Model predictions for auditability.

- Stores: uncalibrated_proba, calibrated_proba, model_version

#### `decision_logs`

Final business decisions with thresholds.

- Stores: decision (APPROVE/REVIEW/REJECT), calibrated_proba, thresholds

### Feature Snapshot

#### `features_snapshot_v1`

Materialized table containing all features needed for modeling. This is what your Python scripts read from.

**Numeric Features:**

- `loan_amount`: Loan amount in dollars
- `income`: Borrower income in dollars
- `loan_to_value_num`: Loan-to-value ratio (numeric, NULL if missing/invalid)
- `dti_num`: Debt-to-income ratio (numeric, NULL if missing/invalid)

**Categorical Features:**

- `income_bucket`: LOW, MID, HIGH, VERY_HIGH, UNKNOWN
- `ltv_bucket`: LOW_LTV, MEDIUM_LTV, HIGH_LTV, VERY_HIGH_LTV, UNKNOWN
- `dti_bucket`: LOW_DTI, MEDIUM_DTI, HIGH_DTI, VERY_HIGH_DTI, UNKNOWN

**Missing Flags:**

- `income_missing_flag`: 1 if income is NULL, 0 otherwise
- `ltv_missing_flag`: 1 if LTV is missing/invalid, 0 otherwise
- `dti_missing_flag`: 1 if DTI is missing/invalid, 0 otherwise

**Target Variable:**

- `risk_label`: 0 = approved (action_taken=1), 1 = denied (action_taken=3)

## Feature Engineering Logic

### Income Buckets

```sql
LOW: income < $50,000
MID: $50,000 ≤ income < $100,000
HIGH: $100,000 ≤ income < $200,000
VERY_HIGH: income ≥ $200,000
UNKNOWN: income IS NULL
```

### LTV Buckets

```sql
LOW_LTV: LTV < 60%
MEDIUM_LTV: 60% ≤ LTV < 80%
HIGH_LTV: 80% ≤ LTV < 95%
VERY_HIGH_LTV: LTV ≥ 95%
UNKNOWN: LTV missing or invalid
```

### DTI Buckets

```sql
LOW_DTI: DTI < 30%
MEDIUM_DTI: 30% ≤ DTI < 43%
HIGH_DTI: 43% ≤ DTI < 50%
VERY_HIGH_DTI: DTI ≥ 50%
UNKNOWN: DTI missing or invalid
```

### Risk Label

```sql
risk_label = 0 if action_taken = 1 (approved)
risk_label = 1 if action_taken = 3 (denied)
```

## Data Quality Notes

1. **HMDA Special Codes**: The raw data may contain special codes (e.g., "Exempt", "NA") in numeric fields. These are converted to NULL and flagged with missing flags.

2. **Duplicate Handling**: The `02_populate_normalized_tables.sql` script uses `DISTINCT ON` to handle potential duplicates in the raw data.

3. **Data Types**:
   - Numeric fields use `NUMERIC(precision, scale)` for exact decimal representation
   - String fields use `VARCHAR` with appropriate lengths

## Maintenance

### Refresh Feature Snapshot

If you update the underlying tables, refresh the snapshot:

```sql
DROP TABLE features_snapshot_v1;
\i sql/03_create_feature_snapshot.sql
```

### Check Data Quality

Run these queries to verify data quality:

```sql
-- Check for NULLs in critical fields
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN loan_amount IS NULL THEN 1 ELSE 0 END) AS null_loan_amount,
    SUM(CASE WHEN income IS NULL THEN 1 ELSE 0 END) AS null_income,
    SUM(CASE WHEN risk_label IS NULL THEN 1 ELSE 0 END) AS null_risk_label
FROM features_snapshot_v1;

-- Check bucket distributions
SELECT income_bucket, COUNT(*)
FROM features_snapshot_v1
GROUP BY income_bucket
ORDER BY income_bucket;
```

## Performance Considerations

- Indexes are created on foreign keys and frequently queried columns
- `features_snapshot_v1` is a materialized table (not a view) for faster reads
- Consider partitioning `loan_applications` by `activity_year` if data volume is very large

## Next Steps

After running these scripts:

1. Verify data quality using the verification queries in each script
2. Run your Python modeling scripts (`baseline_logistic.py`, `calibrated_logistic.py`)
3. The models will read from `features_snapshot_v1`
