from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="quake_pipeline",
    schedule_interval="@hourly",
    start_date=datetime(2026, 6, 23),
    catchup=False,
) as dag:
    ingest = BashOperator(
        task_id="ingest",
        bash_command="cd /opt/airflow/project/ && python3 ingest.py",
    )
    
    clean = BashOperator(
        task_id="clean",
        bash_command="cd /opt/airflow/project && python3 -c \"import duckdb; con = duckdb.connect('md:quake_pro'); con.execute(open('transforms/clean_earthquakes.sql').read())\"",
    )

    aggregate = BashOperator(
        task_id="aggregate",
        bash_command="cd /opt/airflow/project && python3 -c \"import duckdb; con = duckdb.connect('md:quake_pro'); con.execute(open('transforms/daily_summary.sql').read()); con.execute(open('transforms/regional_activity.sql').read())\"",
    )


    forecast = BashOperator(
        task_id="forecast",
        bash_command="cd /opt/airflow/project/ && python3 gr-model.py",
    )

    ingest >> clean >> aggregate >> forecast



