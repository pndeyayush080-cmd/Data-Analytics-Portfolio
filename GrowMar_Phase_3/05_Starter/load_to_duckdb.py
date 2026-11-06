"""Loads every CSV in ../03_Data/csv into a local DuckDB file as schema 'raw'.  Run:  python load_to_duckdb.py
This is only the 'bronze' copy of the exports. PQ-01 (ETL) and PQ-02 (warehouse) are YOUR job: validate, clean, then build the star schema on top.
Open the result with any SQL tool, or:  duckdb pulseiq.duckdb"""
import duckdb, glob, os
con = duckdb.connect("pulseiq.duckdb"); con.execute("CREATE SCHEMA IF NOT EXISTS raw")
for f in sorted(glob.glob("../03_Data/csv/*.csv")):
    t = os.path.basename(f)[:-4]
    con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS SELECT * FROM read_csv_auto('{f}', header=true)")
    print(f"raw.{t:<32}{con.execute(f'select count(*) from raw.{t}').fetchone()[0]:>8} rows")
