-- ============================================================================
-- Populate Normalized Tables from Raw HMDA Data
-- Purpose: Transform hmda_applications_raw into normalized schema
-- ============================================================================

-- Clear existing data (optional - comment out if you want to append)
-- TRUNCATE TABLE borrower_profiles CASCADE;
-- TRUNCATE TABLE credit_attributes CASCADE;
-- TRUNCATE TABLE loan_applications CASCADE;

-- ============================================================================
-- Step 1: Populate loan_applications
-- ============================================================================

-- Use ROW_NUMBER to handle duplicates, keeping the first occurrence
INSERT INTO loan_applications (
    activity_year,
    lei,
    state_code,
    county_code,
    census_tract,
    loan_type,
    loan_purpose,
    action_taken,
    loan_amount,
    loan_to_value_ratio,
    -- Cast interest_rate to numeric; HMDA can store 'Exempt'/'NA' as text
    interest_rate,
    -- Cast loan_term to integer; HMDA can store text codes
    loan_term,
    -- Cast property_value to numeric; HMDA can store 'Exempt'/'NA' as text
    property_value,
    occupancy_type
)
SELECT 
    activity_year,
    lei,
    state_code,
    county_code,
    census_tract,
    loan_type,
    loan_purpose,
    action_taken,
    loan_amount,
    -- Truncate LTV text to fit VARCHAR(10)
    SUBSTRING(loan_to_value_ratio FOR 10) AS loan_to_value_ratio,
    CASE 
        WHEN interest_rate ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(interest_rate AS NUMERIC(6,3))
        ELSE NULL
    END AS interest_rate,
    CASE
        WHEN loan_term ~ '^[0-9]+$'
        THEN CAST(loan_term AS INTEGER)
        ELSE NULL
    END AS loan_term,
    CASE 
        WHEN property_value ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(property_value AS NUMERIC(12,2))
        ELSE NULL
    END AS property_value,
    occupancy_type
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY 
                activity_year,
                lei,
                state_code,
                CAST(county_code AS TEXT),
                CAST(census_tract AS TEXT),
                loan_amount, loan_purpose, action_taken
            ORDER BY activity_year, lei
        ) AS rn
    FROM hmda_applications_raw
) ranked
WHERE rn = 1;

-- ============================================================================
-- Step 2: Populate borrower_profiles
-- ============================================================================

-- Join using the same deduplication logic to ensure 1:1 mapping
INSERT INTO borrower_profiles (
    application_id,
    income,
    debt_to_income_ratio,
    derived_ethnicity,
    derived_race,
    derived_sex,
    applicant_age,
    tract_minority_population_percent,
    ffiec_msa_md_median_family_income,
    tract_to_msa_income_percentage
)
SELECT 
    la.application_id,
    -- Cast income to numeric; handle text codes
    CASE 
        WHEN raw.income ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(raw.income AS NUMERIC(12,2))
        ELSE NULL
    END AS income,
    -- Truncate DTI text to fit VARCHAR(10)
    SUBSTRING(raw.debt_to_income_ratio FOR 10) AS debt_to_income_ratio,
    raw.derived_ethnicity,
    raw.derived_race,
    raw.derived_sex,
    -- Cast applicant_age to integer; handle text codes
    CASE
        WHEN raw.applicant_age ~ '^[0-9]+$'
        THEN CAST(raw.applicant_age AS INTEGER)
        ELSE NULL
    END AS applicant_age,
    -- Cast geographic context fields to numeric; handle text codes
    CASE 
        WHEN raw.tract_minority_population_percent ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(raw.tract_minority_population_percent AS NUMERIC(5,2))
        ELSE NULL
    END AS tract_minority_population_percent,
    CASE 
        WHEN raw.ffiec_msa_md_median_family_income ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(raw.ffiec_msa_md_median_family_income AS NUMERIC(12,2))
        ELSE NULL
    END AS ffiec_msa_md_median_family_income,
    CASE 
        WHEN raw.tract_to_msa_income_percentage ~ '^[0-9]+\\.?[0-9]*$'
        THEN CAST(raw.tract_to_msa_income_percentage AS NUMERIC(5,2))
        ELSE NULL
    END AS tract_to_msa_income_percentage
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY 
                activity_year,
                lei,
                state_code,
                CAST(county_code AS TEXT),
                CAST(census_tract AS TEXT),
                loan_amount, loan_purpose, action_taken
            ORDER BY activity_year, lei
        ) AS rn
    FROM hmda_applications_raw
) raw
INNER JOIN loan_applications la ON (
    la.activity_year = raw.activity_year
    AND la.lei = raw.lei
    AND la.state_code = raw.state_code
    AND la.county_code = CAST(raw.county_code AS TEXT)
    AND la.census_tract = CAST(raw.census_tract AS TEXT)
    AND la.loan_amount = raw.loan_amount
    AND la.loan_purpose = raw.loan_purpose
    AND la.action_taken = raw.action_taken
)
WHERE raw.rn = 1;

-- ============================================================================
-- Step 3: Populate credit_attributes with feature engineering
-- ============================================================================

INSERT INTO credit_attributes (
    application_id,
    loan_to_value_num,
    dti_num,
    income_bucket,
    ltv_bucket,
    dti_bucket,
    income_missing_flag,
    ltv_missing_flag,
    dti_missing_flag,
    risk_label
)
SELECT 
    la.application_id,
    
    -- Convert loan_to_value_ratio to numeric (handle special codes)
    CASE 
        WHEN raw.loan_to_value_ratio ~ '^[0-9]+\.?[0-9]*$' 
        THEN CAST(raw.loan_to_value_ratio AS NUMERIC)
        ELSE NULL
    END AS loan_to_value_num,
    
    -- Convert debt_to_income_ratio to numeric (handle special codes)
    CASE 
        WHEN raw.debt_to_income_ratio ~ '^[0-9]+\.?[0-9]*$' 
        THEN CAST(raw.debt_to_income_ratio AS NUMERIC)
        ELSE NULL
    END AS dti_num,
    
    -- Income buckets (based on percentiles or fixed thresholds)
    CASE 
        WHEN raw.income IS NULL THEN 'UNKNOWN'
        WHEN raw.income < 50000 THEN 'LOW'
        WHEN raw.income < 100000 THEN 'MID'
        WHEN raw.income < 200000 THEN 'HIGH'
        ELSE 'VERY_HIGH'
    END AS income_bucket,
    
    -- LTV buckets
    CASE 
        WHEN raw.loan_to_value_ratio ~ '^[0-9]+\.?[0-9]*$' THEN
            CASE 
                WHEN CAST(raw.loan_to_value_ratio AS NUMERIC) < 60 THEN 'LOW_LTV'
                WHEN CAST(raw.loan_to_value_ratio AS NUMERIC) < 80 THEN 'MEDIUM_LTV'
                WHEN CAST(raw.loan_to_value_ratio AS NUMERIC) < 95 THEN 'HIGH_LTV'
                ELSE 'VERY_HIGH_LTV'
            END
        ELSE 'UNKNOWN'
    END AS ltv_bucket,
    
    -- DTI buckets
    CASE 
        WHEN raw.debt_to_income_ratio ~ '^[0-9]+\.?[0-9]*$' THEN
            CASE 
                WHEN CAST(raw.debt_to_income_ratio AS NUMERIC) < 30 THEN 'LOW_DTI'
                WHEN CAST(raw.debt_to_income_ratio AS NUMERIC) < 43 THEN 'MEDIUM_DTI'
                WHEN CAST(raw.debt_to_income_ratio AS NUMERIC) < 50 THEN 'HIGH_DTI'
                ELSE 'VERY_HIGH_DTI'
            END
        ELSE 'UNKNOWN'
    END AS dti_bucket,
    
    -- Missing flags
    CASE WHEN raw.income IS NULL THEN 1 ELSE 0 END AS income_missing_flag,
    CASE WHEN raw.loan_to_value_ratio IS NULL OR raw.loan_to_value_ratio NOT SIMILAR TO '[0-9]+\.?[0-9]*' THEN 1 ELSE 0 END AS ltv_missing_flag,
    CASE WHEN raw.debt_to_income_ratio IS NULL OR raw.debt_to_income_ratio NOT SIMILAR TO '[0-9]+\.?[0-9]*' THEN 1 ELSE 0 END AS dti_missing_flag,
    
    -- Risk label: 1 = denied (action_taken=3), 0 = approved (action_taken=1)
    CASE WHEN raw.action_taken = 3 THEN 1 ELSE 0 END AS risk_label
    
FROM loan_applications la
INNER JOIN (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY 
                activity_year,
                lei,
                state_code,
                CAST(county_code AS TEXT),
                CAST(census_tract AS TEXT),
                loan_amount, loan_purpose, action_taken
            ORDER BY activity_year, lei
        ) AS rn
    FROM hmda_applications_raw
) raw ON (
    la.activity_year = raw.activity_year
    AND la.lei = raw.lei
    AND la.state_code = raw.state_code
    AND la.county_code = CAST(raw.county_code AS TEXT)
    AND la.census_tract = CAST(raw.census_tract AS TEXT)
    AND la.loan_amount = raw.loan_amount
    AND la.loan_purpose = raw.loan_purpose
    AND la.action_taken = raw.action_taken
)
WHERE raw.rn = 1;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check row counts
SELECT 
    'loan_applications' AS table_name, 
    COUNT(*) AS row_count 
FROM loan_applications
UNION ALL
SELECT 
    'borrower_profiles' AS table_name, 
    COUNT(*) AS row_count 
FROM borrower_profiles
UNION ALL
SELECT 
    'credit_attributes' AS table_name, 
    COUNT(*) AS row_count 
FROM credit_attributes;

-- Check risk label distribution
SELECT 
    risk_label,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM credit_attributes
GROUP BY risk_label
ORDER BY risk_label;

-- Check bucket distributions
SELECT 
    'income_bucket' AS bucket_type,
    income_bucket AS bucket_value,
    COUNT(*) AS count
FROM credit_attributes
GROUP BY income_bucket
UNION ALL
SELECT 
    'ltv_bucket' AS bucket_type,
    ltv_bucket AS bucket_value,
    COUNT(*) AS count
FROM credit_attributes
GROUP BY ltv_bucket
UNION ALL
SELECT 
    'dti_bucket' AS bucket_type,
    dti_bucket AS bucket_value,
    COUNT(*) AS count
FROM credit_attributes
GROUP BY dti_bucket
ORDER BY bucket_type, bucket_value;
