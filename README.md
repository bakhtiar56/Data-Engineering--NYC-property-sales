# NYC Sales Data Engineering & Analytics Project (Airflow + SQL + Power BI)

End-to-end data engineering and analytics project for NYC property sales. The pipeline is fully automated with an **Airflow DAG** that downloads raw data, ingests it, cleans/transforms it, and produces **staged + analytics-ready tables/views** used by a **Power BI dashboard**.

> Note: The dashboard screenshot is intentionally not included here — add your latest image to the README when ready.

---

## Project Overview

This project builds a reproducible workflow that supports **all years** of NYC sales data with **automatic yearly refresh**. The Airflow DAG handles the entire process:

- Downloading source files
- Ingesting into the database
- Cleaning and transforming records
- Staging curated datasets
- Creating aggregated views, indexes, and a unified fact view for BI

---

## Key Features

### Data Pipeline (Airflow)
- Automated orchestration via **Airflow DAG**
- Supports **multi-year** data and yearly refresh
- End-to-end pipeline steps:
  - **Download** raw NYC sales data
  - **Ingest** into raw tables
  - **Process/Clean**
    - Deleted rows with missing values
    - Fixed and standardized **date formats** (consistent across years)
  - **Stage** clean datasets for analytics consumption
  - Build analytics structures:
    - Aggregated table views
    - Indexes for faster filtering and joins

### Data Modeling (SQL)
Created multiple aggregated views and indexes with respect to:
- **neighbourhood**
- **monthly_sales**
- **building_class_category**

Also created a unified fact view:

- **`sales_fact`**: incorporates all relevant variables using joins, serving as the primary source for BI queries.

### Dashboard (Power BI)
- Built an interactive dashboard using:
  - Visualizations and charts
  - Filters, slicers, and tooltips
  - DAX fields/measures
  - Consistent styling for a clean, professional look

---

## Data Outputs

Typical outputs produced by the pipeline include:
- Raw tables (ingested)
- Clean/staging tables
- Aggregated views (neighborhood, monthly sales, building class category)
- `sales_fact` view (BI-ready joined dataset)
- Performance indexes aligned to common query patterns

---

## How It Works (High Level)

1. **Airflow DAG runs** (scheduled or manual trigger)
2. Raw sales data is **downloaded**
3. Data is **ingested** into the database
4. Cleaning/transformation:
   - remove missing-value rows
   - normalize date formats
5. Create/refresh staging + analytics objects:
   - aggregated views
   - indexes
   - `sales_fact` view
6. Power BI connects to the curated layer for reporting

---

## Repo Structure (example)

Adjust this section to match your actual folders:

- `airflow/` — DAGs and pipeline logic  
- `sql/` — table/view definitions, indexes, transformations  
- `powerbi/` — Power BI report file (`.pbix`) and assets  
- `docs/` — screenshots, notes, diagrams  

---

## Dashboard

Add your screenshot here, for example:

```md
![NYC Sales Dashboard](docs/dashboard.png)
```

---

## Notes

- The pipeline is designed to support **all years** and refresh automatically by year.
- The DAG performs downloading, ingesting, processing, cleaning, and staging.
- Rows with missing values are removed.
- Date formats are fixed and made consistent.
- Aggregated views and indexes are built around neighborhood, monthly sales, and building class category.
- A consolidated `sales_fact` view is created via joins to support BI analytics.
- Power BI uses slicers, tooltips, filters, and DAX measures with styled visuals.

---

## License

Add a license here if you plan to open-source this project (MIT is a common choice).