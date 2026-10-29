"""
Day 2: Automated Enterprise Schema & Data Quality Profiler.
Scans DuckDB tables to extract column types, null rates, cardinality,
duplicate row warnings, and sample categorical values into a compact
JSON context for downstream LLM Text-to-SQL generation.
"""

import json
from pathlib import Path
import duckdb


def profile_warehouse(
    db_path: str = "data/insurance_warehouse.duckdb",
    output_path: str = "data/schema_context.json",
) -> dict:
    con = duckdb.connect(db_path, read_only=True)
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]

    warehouse_profile = {"database": db_path, "tables": {}}

    for table in tables:
        total_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        columns_info = con.execute(f"DESCRIBE {table}").fetchall()

        col_profiles = []
        data_quality_warnings = []

        for col_name, col_type, *_ in columns_info:
            # Calculate NULL count and distinct cardinality
            null_count, distinct_count = con.execute(
                f"SELECT COUNT(*) - COUNT({col_name}), COUNT(DISTINCT {col_name}) FROM {table}"
            ).fetchone()
            null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

            col_data = {
                "column": col_name,
                "type": col_type,
                "null_pct": null_pct,
                "distinct_count": distinct_count,
            }

            # Check if an ID column has duplicate rows
            if col_name.endswith("_id") and distinct_count < total_rows:
                if table == "claims" and col_name == "claim_id":
                    dup_count = total_rows - distinct_count
                    data_quality_warnings.append(
                        f"WARNING: '{col_name}' has {dup_count} duplicate rows ({total_rows} total vs {distinct_count} unique). Use DISTINCT or deduplicate in SQL!"
                    )

            if null_pct > 0:
                data_quality_warnings.append(
                    f"WARNING: '{col_name}' contains {null_count} NULL values ({null_pct}%). Filter with WHERE {col_name} IS NOT NULL when aggregating."
                )

            # Extract sample categorical values if low cardinality VARCHAR
            if "VARCHAR" in col_type and distinct_count <= 20:
                samples = [
                    r[0]
                    for r in con.execute(
                        f"SELECT DISTINCT {col_name} FROM {table} WHERE {col_name} IS NOT NULL LIMIT 6"
                    ).fetchall()
                ]
                col_data["allowed_values"] = samples

            col_profiles.append(col_data)

        warehouse_profile["tables"][table] = {
            "row_count": total_rows,
            "data_quality_warnings": data_quality_warnings,
            "columns": col_profiles,
        }

    con.close()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(warehouse_profile, f, indent=2)

    print(f"\n✅ Schema & Quality Profile saved to {output_path}")
    for t_name, t_info in warehouse_profile["tables"].items():
        print(f"  📌 Table '{t_name}': {t_info['row_count']} rows | {len(t_info['data_quality_warnings'])} quality warnings detected")
        for w in t_info["data_quality_warnings"]:
            print(f"     ⚠️  {w}")

    return warehouse_profile


if __name__ == "__main__":
    profile_warehouse()