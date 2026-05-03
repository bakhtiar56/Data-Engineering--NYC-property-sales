from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator

with DAG(
    dag_id="nyc_property_sales_yearly_refresh",
    description="Append-only yearly refresh: download NYC rolling sales XLSX and load into Postgres DW",
    start_date=datetime(2026, 1, 1),
    schedule="@yearly",
    catchup=False,
    max_active_runs=1,
    tags=["nyc", "real-estate", "dw"],
) as dag:

    YEAR = "{{ data_interval_start.year }}"  # the year being scheduled

    download_xlsx = BashOperator(
        task_id="download_year_xlsx",
        bash_command=(
            "cd /opt/airflow/nyc-property-sales && "
            f"python scripts/download_sales_xlsx.py --year {YEAR} --raw-dir data/raw --overwrite"
        ),
    )

    # staging is transient; truncate every run is fine (facts keep history)
    truncate_staging = PostgresOperator(
        task_id="truncate_staging",
        postgres_conn_id="nyc_sales_postgres",
        sql="TRUNCATE TABLE staging.property_sales_raw;",
    )

    run_ingest = BashOperator(
        task_id="run_ingest_year",
        bash_command=(
            "cd /opt/airflow/nyc-property-sales && "
            f"python scripts/ingest_all.py --year {YEAR} --raw-dir data/raw"
        ),
    )

    create_fact_view = PostgresOperator(
        task_id="create_v_sales_fact",
        postgres_conn_id="nyc_sales_postgres",
        sql="""
        create or replace view dw.v_sales_fact as
        select
          f.sale_id,
          f.source_file,
          f.sale_date,
          d.year,
          d.month,
          d.month_start,
          l.borough,
          l.neighborhood,
          l.zip_code,
          p.building_class_category,
          p.building_class_at_time_of_sale,
          f.sale_price
        from dw.fact_property_sales f
        join dw.dim_date d on d.date_key = f.date_key
        join dw.dim_location l on l.location_key = f.location_key
        join dw.dim_property p on p.property_key = f.property_key;
        """,
    )

    download_xlsx >> truncate_staging >> run_ingest >> create_fact_view