-- ============================================================================
-- Schema Creation Script
-- Purpose: Create normalized tables for credit risk system
-- ============================================================================

-- Drop existing objects if they exist (for clean rebuild)
DROP TABLE IF EXISTS decision_logs CASCADE;
DROP TABLE IF EXISTS model_predictions CASCADE;
-- features_snapshot_v1 may exist as a VIEW or a TABLE from prior runs
DROP VIEW IF EXISTS features_snapshot_v1 CASCADE;
DROP TABLE IF EXISTS features_snapshot_v1 CASCADE;
DROP TABLE IF EXISTS loan_applications CASCADE;
DROP TABLE IF EXISTS borrower_profiles CASCADE;
DROP TABLE IF EXISTS credit_attributes CASCADE;

-- ============================================================================
-- Core Tables
-- ============================================================================

-- loan_applications: Core loan application data
CREATE TABLE loan_applications (
    application_id SERIAL PRIMARY KEY,
    activity_year INTEGER,
    lei VARCHAR(20),
    state_code VARCHAR(2),
    county_code VARCHAR(5),
    census_tract VARCHAR(11),
    
    -- Loan characteristics
    loan_type INTEGER,
    loan_purpose INTEGER,
    action_taken INTEGER,
    loan_amount NUMERIC(12, 2),
    loan_to_value_ratio VARCHAR(10),  -- Can be numeric or special codes
    interest_rate NUMERIC(6, 3),
    loan_term INTEGER,
    property_value NUMERIC(12, 2),
    occupancy_type INTEGER,
    
    -- Application metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- borrower_profiles: Borrower demographic and income information
CREATE TABLE borrower_profiles (
    profile_id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(application_id) ON DELETE CASCADE,
    
    -- Income information
    income NUMERIC(12, 2),
    debt_to_income_ratio VARCHAR(10),  -- Can be numeric or special codes
    
    -- Demographics (for fairness analysis)
    derived_ethnicity VARCHAR(50),
    derived_race VARCHAR(50),
    derived_sex VARCHAR(10),
    applicant_age INTEGER,
    
    -- Geographic context
    tract_minority_population_percent NUMERIC(5, 2),
    ffiec_msa_md_median_family_income NUMERIC(12, 2),
    tract_to_msa_income_percentage NUMERIC(5, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- credit_attributes: Derived credit risk attributes
CREATE TABLE credit_attributes (
    attribute_id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(application_id) ON DELETE CASCADE,
    
    -- Derived numeric features
    loan_to_value_num NUMERIC(5, 2),
    dti_num NUMERIC(5, 2),
    
    -- Buckets
    income_bucket VARCHAR(20),
    ltv_bucket VARCHAR(20),
    dti_bucket VARCHAR(20),
    
    -- Missing flags
    income_missing_flag INTEGER DEFAULT 0,
    ltv_missing_flag INTEGER DEFAULT 0,
    dti_missing_flag INTEGER DEFAULT 0,
    
    -- Target variable
    risk_label INTEGER,  -- 0 = approved (action_taken=1), 1 = denied (action_taken=3)
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Model and Decision Tables
-- ============================================================================

-- model_predictions: Store model predictions for auditability
CREATE TABLE model_predictions (
    prediction_id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(application_id) ON DELETE SET NULL,
    
    uncalibrated_proba NUMERIC(6, 5),
    calibrated_proba NUMERIC(6, 5),
    model_version VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- decision_logs: Store final business decisions
CREATE TABLE decision_logs (
    decision_id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES loan_applications(application_id) ON DELETE SET NULL,
    prediction_id INTEGER REFERENCES model_predictions(prediction_id) ON DELETE SET NULL,
    
    decision VARCHAR(20),  -- APPROVE, REVIEW, REJECT
    calibrated_proba NUMERIC(6, 5),
    threshold_approve NUMERIC(4, 2),
    threshold_review NUMERIC(4, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX idx_loan_applications_action_taken ON loan_applications(action_taken);
CREATE INDEX idx_loan_applications_activity_year ON loan_applications(activity_year);
CREATE INDEX idx_borrower_profiles_application_id ON borrower_profiles(application_id);
CREATE INDEX idx_credit_attributes_application_id ON credit_attributes(application_id);
CREATE INDEX idx_credit_attributes_risk_label ON credit_attributes(risk_label);
CREATE INDEX idx_model_predictions_application_id ON model_predictions(application_id);
CREATE INDEX idx_decision_logs_application_id ON decision_logs(application_id);
CREATE INDEX idx_decision_logs_decision ON decision_logs(decision);

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE loan_applications IS 'Core loan application data from HMDA';
COMMENT ON TABLE borrower_profiles IS 'Borrower demographic and income information';
COMMENT ON TABLE credit_attributes IS 'Engineered features and risk labels for modeling';
COMMENT ON TABLE model_predictions IS 'Model predictions for auditability and monitoring';
COMMENT ON TABLE decision_logs IS 'Final business decisions with thresholds';

COMMENT ON COLUMN credit_attributes.risk_label IS '0 = approved (action_taken=1), 1 = denied (action_taken=3)';
COMMENT ON COLUMN credit_attributes.income_bucket IS 'LOW, MID, HIGH, VERY_HIGH, UNKNOWN';
COMMENT ON COLUMN credit_attributes.ltv_bucket IS 'LOW_LTV, MEDIUM_LTV, HIGH_LTV, VERY_HIGH_LTV, UNKNOWN';
COMMENT ON COLUMN credit_attributes.dti_bucket IS 'LOW_DTI, MEDIUM_DTI, HIGH_DTI, VERY_HIGH_DTI, UNKNOWN';
