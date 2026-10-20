#!/usr/bin/env python3
"""
SQL Pipeline Runner
Purpose: Execute SQL scripts in the correct order to set up the database schema
and populate normalized tables from raw HMDA data.
"""

import os
import sys
from sqlalchemy import create_engine, text
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))

def run_sql_file(engine, filepath):
    """Execute a SQL file against the database."""
    print(f"\n{'='*60}")
    print(f"Executing: {filepath}")
    print(f"{'='*60}")
    
    with open(filepath, 'r') as f:
        sql_content = f.read()
    
    # Execute the entire file as one transaction.
    # Use exec_driver_sql so PostgreSQL can handle multi-statement SQL files.
    with engine.begin() as conn:
        try:
            conn.exec_driver_sql(sql_content)
            print(f"✓ Completed: {filepath}")
        except Exception as e:
            print(f"  Error executing {filepath}: {e}")
            raise

def main():
    """Main execution function."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: Please set DATABASE_URL environment variable")
        print("Example: export DATABASE_URL='postgresql://user:pass@localhost:5432/hmda'")
        sys.exit(1)
    
    # Create engine
    print(f"Connecting to database...")
    engine = create_engine(database_url)
    
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)
    
    # Get SQL directory
    sql_dir = Path(__file__).parent
    
    # Scripts to run in order
    scripts = [
        sql_dir / "01_create_schema.sql",
        sql_dir / "02_populate_normalized_tables.sql",
        sql_dir / "03_create_feature_snapshot.sql"
    ]
    
    # Verify all scripts exist
    for script in scripts:
        if not script.exists():
            print(f"ERROR: Script not found: {script}")
            sys.exit(1)
    
    # Run scripts
    print(f"\n{'='*60}")
    print("SQL Pipeline Execution")
    print(f"{'='*60}")
    print(f"Will execute {len(scripts)} scripts in order")
    
    for script in scripts:
        try:
            run_sql_file(engine, script)
        except Exception as e:
            print(f"\nERROR: Failed to execute {script}")
            print(f"Error: {e}")
            sys.exit(1)
    
    print(f"\n{'='*60}")
    print("✓ SQL Pipeline Completed Successfully!")
    print(f"{'='*60}")
    
    # Run verification queries
    print("\nRunning verification queries...")
    try:
        with engine.connect() as conn:
            # Check table counts
            result = conn.execute(text("""
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
                FROM credit_attributes
                UNION ALL
                SELECT 
                    'features_snapshot_v1' AS table_name, 
                    COUNT(*) AS row_count 
                FROM features_snapshot_v1
            """))
            
            print("\nTable Row Counts:")
            for row in result:
                print(f"  {row[0]}: {row[1]:,} rows")
            
            # Check risk label distribution
            result = conn.execute(text("""
                SELECT 
                    risk_label,
                    COUNT(*) AS count,
                    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
                FROM features_snapshot_v1
                GROUP BY risk_label
                ORDER BY risk_label
            """))
            
            print("\nRisk Label Distribution:")
            for row in result:
                label = "Denied" if row[0] == 1 else "Approved"
                print(f"  {label}: {row[1]:,} ({row[2]}%)")
                
    except Exception as e:
        print(f"Warning: Could not run verification queries: {e}")

if __name__ == "__main__":
    main()
