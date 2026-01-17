import pandas as pd
from sqlalchemy import create_engine
from config import SELECTED_COLUMNS

engine = create_engine(
        "postgresql://<username>:<password>@<host>:<port>/<database>"

)

CSV_PATH = "loan_purposes_1-31_year_2024.csv"
CHUNKSIZE = 200_000

for i, chunk in enumerate(
    pd.read_csv(CSV_PATH, chunksize=CHUNKSIZE, low_memory=False)
):
    # row-level filters
    chunk = chunk[
        chunk["loan_purpose"].isin([1, 3]) &   # home purchase, refinance
        chunk["loan_type"].isin([1]) &          # conventional
        chunk["action_taken"].isin([1, 3])      # approved, denied
    ]

    # column reduction
    chunk = chunk[SELECTED_COLUMNS]

    # write to postgres
    chunk.to_sql(
        "hmda_applications_raw",
        engine,
        if_exists="append",
        index=False,
        method="multi"
    )

    print(f"Chunk {i} loaded, rows: {len(chunk)}")
