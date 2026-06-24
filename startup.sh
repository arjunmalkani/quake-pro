#!/bin/bash
set -e

mkdir -p data/raw

echo "Running ingest..."
python ingest.py

echo "Running transforms..."
python3 -c "
import duckdb
con = duckdb.connect('data/earthquake_data.duckdb')
con.execute(open('transforms/clean_earthquakes.sql').read())
con.execute(open('transforms/daily_summary.sql').read())
con.execute(open('transforms/regional_activity.sql').read())
con.close()
"

echo "Running forecast model..."
python gr-model.py

echo "Starting API server..."
cd backend && uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
