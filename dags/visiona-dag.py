from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='data_ingestion_scheduled_update',
    default_args=default_args,
    description='Executa o script data-ingestion/main.py para atualizar os dados',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['data-ingestion', 'etl'],
) as dag:
    run_data_ingestion = BashOperator(
        task_id='run_data_ingestion_script',
        bash_command='python /opt/airflow/data-ingestion/main.py',
    )