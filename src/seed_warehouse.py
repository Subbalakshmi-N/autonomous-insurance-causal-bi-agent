"""
Day 1: Enterprise Insurance & Marketing Attribution Warehouse Generator.
Creates a multi-table DuckDB database with realistic risk/CLV metrics,
intentional enterprise data quality issues (duplicates/nulls), and a Q3 claims spike
for downstream Text-to-SQL and Statistical Root-Cause analysis.
"""

from pathlib import Path
import duckdb
import numpy as np
import pandas as pd


def build_warehouse(db_path: str = "data/insurance_warehouse.duckdb") -> None:
    # Set seed so results are 100% reproducible
    np.random.seed(42)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # 1. Generate CUSTOMERS & POLICIES table (5,000 policies)
    # ---------------------------------------------------------
    n_policies = 5000
    regions = ["Hesse (Frankfurt)", "Bavaria (Munich)", "Berlin", "NRW (Cologne)", "Hamburg"]
    tiers = ["Preferred", "Standard", "High-Risk"]
    channels = ["Paid_Search", "Affiliate_Partner", "Direct_Web", "Broker_Network"]

    policy_ids = [f"POL-{10000 + i}" for i in range(n_policies)]
    customer_ids = [f"CUST-{50000 + i}" for i in range(n_policies)]
    chosen_tiers = np.random.choice(tiers, size=n_policies, p=[0.45, 0.40, 0.15])
    chosen_regions = np.random.choice(regions, size=n_policies, p=[0.30, 0.25, 0.15, 0.20, 0.10])
    chosen_channels = np.random.choice(channels, size=n_policies, p=[0.35, 0.25, 0.25, 0.15])

    # Base premium depends on underwriting risk tier
    tier_multiplier = {"Preferred": 650, "Standard": 950, "High-Risk": 1550}
    base_premiums = [
        round(tier_multiplier[t] * np.random.uniform(0.85, 1.25), 2)
        for t in chosen_tiers
    ]

    # Estimate Customer Lifetime Value (CLV)
    clv_estimates = [
        round(prem * np.random.uniform(2.8, 5.2), 2) for prem in base_premiums
    ]

    inception_dates = pd.to_datetime(
        np.random.choice(pd.date_range("2025-01-01", "2026-09-30"), size=n_policies)
    )

    policies_df = pd.DataFrame({
        "policy_id": policy_ids,
        "customer_id": customer_ids,
        "region": chosen_regions,
        "underwriting_tier": chosen_tiers,
        "acquisition_channel": chosen_channels,
        "annual_premium_eur": base_premiums,
        "estimated_clv_eur": clv_estimates,
        "inception_date": inception_dates,
        "is_active": np.random.choice([True, False], size=n_policies, p=[0.88, 0.12]),
    })

    # ---------------------------------------------------------
    # 2. Generate CLAIMS table (~1,800 claims + Q3 anomaly + messy duplicates)
    # ---------------------------------------------------------
    n_claims = 1800
    sampled_policies = policies_df.sample(n=n_claims, replace=True, random_state=42)
    claim_dates = pd.to_datetime(
        np.random.choice(pd.date_range("2026-01-01", "2026-09-30"), size=n_claims)
    )

    claim_amounts = []
    for region, channel, c_date in zip(
        sampled_policies["region"],
        sampled_policies["acquisition_channel"],
        claim_dates,
    ):
        base_claim = np.random.gamma(shape=2.2, scale=650.0)
        # Inject a statistically significant Q3 anomaly in Affiliate_Partner channel
        if c_date.month in [7, 8, 9] and channel == "Affiliate_Partner":
            base_claim *= 2.35
        claim_amounts.append(round(base_claim, 2))

    claims_df = pd.DataFrame({
        "claim_id": [f"CLM-{80000 + i}" for i in range(n_claims)],
        "policy_id": sampled_policies["policy_id"].values,
        "claim_date": claim_dates,
        "claim_type": np.random.choice(
            ["Collision", "Comprehensive_Weather", "Glass_Repair", "Liability"],
            size=n_claims,
            p=[0.40, 0.25, 0.20, 0.15],
        ),
        "claim_amount_eur": claim_amounts,
        "settlement_status": np.random.choice(
            ["Paid", "Pending_Review", "Flagged_SIU"], size=n_claims, p=[0.78, 0.15, 0.07]
        ),
    })

    # Inject realistic enterprise messiness: 25 duplicate rows and 30 NULL claim dates
    duplicates = claims_df.sample(n=25, random_state=42)
    claims_df = pd.concat([claims_df, duplicates], ignore_index=True)
    null_indices = np.random.choice(claims_df.index, size=30, replace=False)
    claims_df.loc[null_indices, "claim_date"] = pd.NaT

    # ---------------------------------------------------------
    # 3. Generate MARKETING_CAMPAIGNS table (Multi-Touch Attribution)
    # ---------------------------------------------------------
    n_touches = 8000
    touches_df = pd.DataFrame({
        "touch_id": [f"TCH-{200000 + i}" for i in range(n_touches)],
        "customer_id": np.random.choice(customer_ids, size=n_touches),
        "channel": np.random.choice(channels, size=n_touches, p=[0.40, 0.30, 0.20, 0.10]),
        "ad_spend_eur": np.round(np.random.uniform(4.5, 48.0, size=n_touches), 2),
        "touch_date": pd.to_datetime(
            np.random.choice(pd.date_range("2025-11-01", "2026-09-30"), size=n_touches)
        ),
        "converted_to_quote": np.random.choice([1, 0], size=n_touches, p=[0.22, 0.78]),
    })

    # ---------------------------------------------------------
    # 4. Save all tables into DuckDB Warehouse
    # ---------------------------------------------------------
    con = duckdb.connect(db_path)
    con.execute("CREATE OR REPLACE TABLE policies AS SELECT * FROM policies_df")
    con.execute("CREATE OR REPLACE TABLE claims AS SELECT * FROM claims_df")
    con.execute("CREATE OR REPLACE TABLE marketing_touches AS SELECT * FROM touches_df")

    # Quick sanity check summary printed to terminal
    summary = con.execute("""
        SELECT 
            (SELECT COUNT(*) FROM policies) AS total_policies,
            (SELECT COUNT(*) FROM claims) AS total_claims_raw,
            (SELECT COUNT(DISTINCT claim_id) FROM claims) AS unique_claims,
            (SELECT COUNT(*) FROM marketing_touches) AS total_marketing_touches
    """).df()

    print("\n✅ DuckDB Insurance & Attribution Warehouse Created Successfully!")
    print(summary.to_string(index=False))
    con.close()


if __name__ == "__main__":
    build_warehouse()