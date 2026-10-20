-- ============================================================================
-- Create Feature Snapshot View/Table
-- Purpose: Create features_snapshot_v1 for modeling
-- This is the table that your Python models read from
-- ============================================================================

-- Drop existing snapshot if it exists
DROP TABLE IF EXISTS features_snapshot_v1 CASCADE;

-- Create materialized view (table) for modeling
CREATE TABLE features_snapshot_v1 AS
SELECT 
    -- Application ID for joining
    la.application_id,
    
    -- Numeric features
    la.loan_amount,
    bp.income,
    ca.loan_to_value_num,
    ca.dti_num,
    
    -- Categorical buckets
    ca.income_bucket,
    ca.ltv_bucket,
    ca.dti_bucket,
    
    -- Missing flags
    ca.income_missing_flag,
    ca.ltv_missing_flag,
    ca.dti_missing_flag,
    
    -- Target variable
    ca.risk_label,
    
    -- Additional features for potential future use
    la.interest_rate,
    la.loan_term,
    la.property_value,
    bp.applicant_age,
    bp.tract_minority_population_percent,
    bp.ffiec_msa_md_median_family_income,
    bp.tract_to_msa_income_percentage,
    
    -- Metadata
    la.activity_year,
    la.state_code,
    la.loan_purpose,
    la.action_taken
    
FROM loan_applications la
INNER JOIN borrower_profiles bp ON la.application_id = bp.application_id
INNER JOIN credit_attributes ca ON la.application_id = ca.application_id
WHERE ca.risk_label IS NOT NULL;  -- Only include records with risk labels

-- Create index for faster queries
CREATE INDEX idx_features_snapshot_v1_application_id ON features_snapshot_v1(application_id);
CREATE INDEX idx_features_snapshot_v1_risk_label ON features_snapshot_v1(risk_label);

-- Add comments
COMMENT ON TABLE features_snapshot_v1 IS 'Feature snapshot v1 for model training and prediction';
COMMENT ON COLUMN features_snapshot_v1.risk_label IS 'Target variable: 0 = approved, 1 = denied';

-- ============================================================================
-- Verification Query
-- ============================================================================

SELECT 
    COUNT(*) AS total_records,
    COUNT(DISTINCT application_id) AS unique_applications,
    SUM(risk_label) AS denied_count,
    COUNT(*) - SUM(risk_label) AS approved_count,
    ROUND(100.0 * SUM(risk_label) / COUNT(*), 2) AS denial_rate_pct
FROM features_snapshot_v1;

-- Show feature distributions
SELECT 
    'loan_amount' AS feature,
    COUNT(*) AS total,
    COUNT(loan_amount) AS non_null,
    ROUND(AVG(loan_amount), 2) AS mean,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY loan_amount), 2) AS median
FROM features_snapshot_v1
UNION ALL
SELECT 
    'income' AS feature,
    COUNT(*) AS total,
    COUNT(income) AS non_null,
    ROUND(AVG(income), 2) AS mean,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY income), 2) AS median
FROM features_snapshot_v1
UNION ALL
SELECT 
    'loan_to_value_num' AS feature,
    COUNT(*) AS total,
    COUNT(loan_to_value_num) AS non_null,
    ROUND(AVG(loan_to_value_num), 2) AS mean,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY loan_to_value_num), 2) AS median
FROM features_snapshot_v1
UNION ALL
SELECT 
    'dti_num' AS feature,
    COUNT(*) AS total,
    COUNT(dti_num) AS non_null,
    ROUND(AVG(dti_num), 2) AS mean,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dti_num), 2) AS median
FROM features_snapshot_v1;
