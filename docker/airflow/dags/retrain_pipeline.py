from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="retrain_fraud_model",
    default_args=default_args,
    description="Auto-retrain LightGBM fraud model daily",
    schedule_interval=timedelta(days=1),
    start_date=datetime(2025, 5, 15),
    catchup=False,
) as dag:

    retrain = BashOperator(
        task_id="retrain_model",
        bash_command="cd /opt/airflow && python model/train_model.py"
    )
    promote = BashOperator(
    task_id="promote_if_better",
    bash_command="cd /app && python model/promote_model.py"
    )



