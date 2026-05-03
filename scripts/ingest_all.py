import os
import glob
import hashlib
import pandas as pd
import psycopg2
import argparse
from psycopg2.extras import execute_values

PG = "postgresql://de_user:de_password@postgres:5432/nyc_sales"

COLMAP = {
    "BOROUGH": "borough",
    "NEIGHBORHOOD": "neighborhood",
    "BUILDING CLASS CATEGORY": "building_class_category",
    "TAX CLASS AT PRESENT": "tax_class_at_present",
    "BLOCK": "block",
    "LOT": "lot",
    "EASE-MENT": "ease_ment",
    "BUILDING CLASS AT PRESENT": "building_class_at_present",
    "ADDRESS": "address",
    "APARTMENT NUMBER": "apartment_number",
    "ZIP CODE": "zip_code",
    "RESIDENTIAL UNITS": "residential_units",
    "COMMERCIAL UNITS": "commercial_units",
    "TOTAL UNITS": "total_units",
    "LAND SQUARE FEET": "land_square_feet",
    "GROSS SQUARE FEET": "gross_square_feet",
    "YEAR BUILT": "year_built",
    "TAX CLASS AT TIME OF SALE": "tax_class_at_time_of_sale",
    "BUILDING CLASS AT TIME OF SALE": "building_class_at_time_of_sale",
    "SALE PRICE": "sale_price",
    "SALE DATE": "sale_date",
}

BOROUGH_MAP = {
    "1": "MANHATTAN", "1.0": "MANHATTAN",
    "2": "BRONX", "2.0": "BRONX",
    "3": "BROOKLYN", "3.0": "BROOKLYN",
    "4": "QUEENS", "4.0": "QUEENS",
    "5": "STATEN ISLAND", "5.0": "STATEN ISLAND",
}

def clean_col(c: str) -> str:
    c = str(c).strip()
    return " ".join(c.split())

def normalize_zip(z):
    if z is None:
        return None
    z = str(z).strip()
    if z == "" or z.lower() == "nan":
        return None
    # 10009 or 10009.0
    if pd.Series([z]).str.match(r"^[0-9]{5}(\.0+)?$").iloc[0]:
        return z[:5]
    return z

def excel_to_df(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    sheet = xl.sheet_names[0]  # each file is 1 borough sheet in this dataset
    df = pd.read_excel(xlsx_path, sheet_name=sheet, skiprows=6, dtype=str)
    df.columns = [clean_col(c) for c in df.columns]
    df = df.dropna(how="all")
    missing = [c for c in COLMAP if c not in df.columns]
    if missing:
        raise ValueError(f"{os.path.basename(xlsx_path)} missing columns: {missing}")
    df = df[list(COLMAP.keys())].rename(columns=COLMAP)
    return df

def compute_hash(row: dict) -> str:
    key = "|".join([
        row.get("source_file","") or "",
        row.get("borough","") or "",
        row.get("block","") or "",
        row.get("lot","") or "",
        row.get("address","") or "",
        row.get("sale_date","") or "",
        row.get("sale_price","") or "",
    ])
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def main():
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--raw-dir", default="data/raw")
    args = ap.parse_args()

    raw_dir = args.raw_dir
    files = sorted(glob.glob(os.path.join(raw_dir, f"{args.year}_*.xlsx")))
    if not files:
        raise SystemExit(f"No {args.year}_*.xlsx files found in {raw_dir}")

    conn = psycopg2.connect(PG)
    cur = conn.cursor()

    for path in files:
        source_file = os.path.basename(path)
        print(f"\n=== Ingesting {source_file} ===")

        df = excel_to_df(path)
        df.insert(0, "source_file", source_file)

        # staging load (fast insert)
        cols = df.columns.tolist()
        values = df.where(pd.notnull(df), None).values.tolist()
        cur.execute("delete from staging.property_sales_raw where source_file = %s", (source_file,))
        conn.commit()
        execute_values(
            cur,
            f"insert into staging.property_sales_raw ({', '.join(cols)}) values %s",
            values,
            page_size=5000
        )
        conn.commit()
        print(f"Loaded staging rows: {len(df)}")

        # Populate dim_date
        cur.execute("""
            insert into dw.dim_date (date_key, full_date, year, month, day, month_start, month_name)
            select
              to_char(s.sale_date::date, 'YYYYMMDD')::int,
              s.sale_date::date,
              extract(year from s.sale_date::date)::int,
              extract(month from s.sale_date::date)::int,
              extract(day from s.sale_date::date)::int,
              date_trunc('month', s.sale_date::date)::date,
              to_char(s.sale_date::date, 'Mon')
            from (
              select distinct sale_date
              from staging.property_sales_raw
              where source_file = %s
            ) s
            on conflict (date_key) do nothing
        """, (source_file,))
        conn.commit()

        # Populate dim_location
        cur.execute("""
            insert into dw.dim_location (borough, neighborhood, zip_code)
            select distinct
              case trim(borough)
                when '1' then 'MANHATTAN' when '1.0' then 'MANHATTAN'
                when '2' then 'BRONX' when '2.0' then 'BRONX'
                when '3' then 'BROOKLYN' when '3.0' then 'BROOKLYN'
                when '4' then 'QUEENS' when '4.0' then 'QUEENS'
                when '5' then 'STATEN ISLAND' when '5.0' then 'STATEN ISLAND'
                else trim(borough)
              end,
              nullif(upper(trim(neighborhood)), ''),
              case
                when nullif(trim(zip_code), '') is null then null
                when trim(zip_code) ~ '^[0-9]{5}(\\.0+)?$' then substring(trim(zip_code) from 1 for 5)
                else trim(zip_code)
              end
            from staging.property_sales_raw
            where source_file = %s
            on conflict (borough, neighborhood, zip_code) do nothing
        """, (source_file,))
        conn.commit()

        # Populate dim_property
        cur.execute("""
            insert into dw.dim_property (
              borough, block, lot, address,
              building_class_at_time_of_sale, building_class_category
            )
            select distinct
              case trim(borough)
                when '1' then 'MANHATTAN' when '1.0' then 'MANHATTAN'
                when '2' then 'BRONX' when '2.0' then 'BRONX'
                when '3' then 'BROOKLYN' when '3.0' then 'BROOKLYN'
                when '4' then 'QUEENS' when '4.0' then 'QUEENS'
                when '5' then 'STATEN ISLAND' when '5.0' then 'STATEN ISLAND'
                else trim(borough)
              end,
              case when trim(block) ~ '^[0-9]+(\\.0+)?$' then trim(block)::numeric::int else null end,
              case when trim(lot)   ~ '^[0-9]+(\\.0+)?$' then trim(lot)::numeric::int else null end,
              nullif(upper(trim(address)), ''),
              nullif(upper(trim(building_class_at_time_of_sale)), ''),
              nullif(upper(trim(building_class_category)), '')
            from staging.property_sales_raw
            where source_file=%s
            on conflict (borough, block, lot, address, building_class_at_time_of_sale) do nothing
        """, (source_file,))
        conn.commit()

        # Load facts excluding sale_price=0, with idempotent hash
        cur.execute("""
            with src as (
              select
                s.source_file,
                case trim(s.borough)
                  when '1' then 'MANHATTAN' when '1.0' then 'MANHATTAN'
                  when '2' then 'BRONX' when '2.0' then 'BRONX'
                  when '3' then 'BROOKLYN' when '3.0' then 'BROOKLYN'
                  when '4' then 'QUEENS' when '4.0' then 'QUEENS'
                  when '5' then 'STATEN ISLAND' when '5.0' then 'STATEN ISLAND'
                  else trim(s.borough)
                end as borough_name,
                nullif(upper(trim(s.neighborhood)), '') as neighborhood_std,
                case
                  when nullif(trim(s.zip_code), '') is null then null
                  when trim(s.zip_code) ~ '^[0-9]{5}(\\.0+)?$' then substring(trim(s.zip_code) from 1 for 5)
                  else trim(s.zip_code)
                end as zip_std,
                case when trim(s.block) ~ '^[0-9]+(\\.0+)?$' then trim(s.block)::numeric::int else null end as block_int,
                case when trim(s.lot)   ~ '^[0-9]+(\\.0+)?$' then trim(s.lot)::numeric::int else null end as lot_int,
                nullif(upper(trim(s.address)), '') as address_std,
                nullif(upper(trim(s.building_class_at_time_of_sale)), '') as bclass_sale,
                s.sale_date::date as sale_date_parsed,
                to_char(s.sale_date::date, 'YYYYMMDD')::int as date_key,
                trim(s.sale_price)::numeric as sale_price_num,
                md5(
                  coalesce(s.source_file,'') || '|' ||
                  coalesce(trim(s.borough),'') || '|' ||
                  coalesce(trim(s.block),'') || '|' ||
                  coalesce(trim(s.lot),'') || '|' ||
                  coalesce(upper(trim(s.address)),'') || '|' ||
                  coalesce(s.sale_date,'') || '|' ||
                  coalesce(trim(s.sale_price),'')
                ) as sale_row_hash
              from staging.property_sales_raw s
              where s.source_file=%s
            ),
            filtered as (
              select * from src where sale_price_num > 0
            )
            insert into dw.fact_property_sales (
              source_file, date_key, location_key, property_key, sale_price, sale_date, sale_row_hash
            )
            select
              f.source_file,
              f.date_key,
              l.location_key,
              p.property_key,
              f.sale_price_num::numeric(14,2),
              f.sale_date_parsed,
              f.sale_row_hash
            from filtered f
            join dw.dim_location l
              on l.borough = f.borough_name
             and l.neighborhood is not distinct from f.neighborhood_std
             and l.zip_code is not distinct from f.zip_std
            join dw.dim_property p
              on p.borough = f.borough_name
             and p.block is not distinct from f.block_int
             and p.lot is not distinct from f.lot_int
             and p.address is not distinct from f.address_std
             and p.building_class_at_time_of_sale is not distinct from f.bclass_sale
            on conflict (sale_row_hash) do nothing
        """, (source_file,))
        conn.commit()

        cur.execute("select count(*) from dw.fact_property_sales where source_file=%s", (source_file,))
        print("Fact rows now:", cur.fetchone()[0])

    cur.close()
    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()