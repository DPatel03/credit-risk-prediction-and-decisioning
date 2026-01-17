### Credit Risk Prediction and Decisioning System

A production-style machine learning system that ingests HMDA data, engineers features, trains calibrated logistic regression models, applies underwriting decision rules, and logs predictions and decisions into PostgreSQL. This project is designed for students, data scientists, and ML engineers who want to learn how real credit risk pipelines are built end to end.

## Installation

Use pip to install dependencies.

```bash
pip install -r requirements.txt
```

## Usage

Run the data ingestion pipeline.

```bash
python data_pipeline/ingest_hmda.py
```

Train the baseline and calibrated models.

```bash
python modeling/baseline_logistic.py
python modeling/calibrated_logistic.py
```

Run the decision engine and log results.

```bash
python modeling/decision_logic.py
```

Set your PostgreSQL connection using an environment variable.

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/hmda"
```

Example of loading the database URL in Python.

```python
import os
ENGINE_URI = os.getenv("DATABASE_URL")
```

## Project Structure

```
credit-risk-prediction-and-decisioning
    data_pipeline
        ingest_hmda.py
    modeling
        baseline_logistic.py
        calibrated_logistic.py
        decision_logic.py
    outputs
    sql
    requirements.txt
    README.md
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.
