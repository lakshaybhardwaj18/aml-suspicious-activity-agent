"""
EDA Tool
--------
Invoked by the Agent Orchestrator only for broad / exploratory queries
(e.g. "give me an overview of transactions in UAE" or "profile the dataset").

Public entry point: run_eda(tx_df, customers_df=None, filters=None) -> dict

The returned dict is JSON-serializable so it can be passed straight back
through the LangChain tool-calling interface to the Explanation Component.
"""

import pandas as pd
import numpy as np


def _basic_profile(df: pd.DataFrame) -> dict:
    """Column-level profile: dtype, missing %, cardinality, basic stats."""
    profile = {}
    for col in df.columns:
        s = df[col]
        col_info = {
            "dtype": str(s.dtype),
            "missing_pct": round(float(s.isna().mean()) * 100, 2),
            "n_unique": int(s.nunique()),
        }
        if pd.api.types.is_numeric_dtype(s):
            col_info.update({
                "mean": round(float(s.mean()), 2),
                "std": round(float(s.std()), 2),
                "min": round(float(s.min()), 2),
                "p50": round(float(s.median()), 2),
                "p95": round(float(s.quantile(0.95)), 2),
                "max": round(float(s.max()), 2),
            })
        elif s.nunique() <= 20:
            col_info["value_counts"] = s.value_counts(dropna=False).to_dict()
        profile[col] = col_info
    return profile


def _baseline_behavior(tx_df: pd.DataFrame) -> dict:
    """Baseline behavior stats used later as reference points by the
    Anomaly Detection Tool (e.g. 'typical' amount, tx frequency per customer)."""
    per_customer = tx_df.groupby("customer_id")["amount"].agg(["count", "sum", "mean"])
    return {
        "overall_amount_mean": round(float(tx_df["amount"].mean()), 2),
        "overall_amount_std": round(float(tx_df["amount"].std()), 2),
        "overall_amount_p95": round(float(tx_df["amount"].quantile(0.95)), 2),
        "overall_amount_p99": round(float(tx_df["amount"].quantile(0.99)), 2),
        "avg_tx_per_customer": round(float(per_customer["count"].mean()), 2),
        "avg_daily_tx_volume": round(float(tx_df.groupby("date").size().mean()), 2)
        if "date" in tx_df.columns else None,
        "suspicious_rate_pct": round(float(tx_df["is_suspicious"].mean()) * 100, 2)
        if "is_suspicious" in tx_df.columns else None,
    }


def _distributions(tx_df: pd.DataFrame) -> dict:
    """Distribution breakdowns by key categorical dimensions."""
    out = {}
    for col in ["transaction_type", "channel", "country"]:
        if col in tx_df.columns:
            out[f"by_{col}"] = tx_df[col].value_counts().to_dict()
    if "pattern_type" in tx_df.columns:
        out["pattern_type_counts"] = tx_df["pattern_type"].value_counts(dropna=True).to_dict()
    if "is_suspicious" in tx_df.columns:
        for col in ["transaction_type", "channel", "country"]:
            if col in tx_df.columns:
                out[f"suspicious_rate_by_{col}"] = (
                    tx_df.groupby(col)["is_suspicious"].mean().mul(100).round(2).to_dict()
                )
    return out


def apply_filters(tx_df: pd.DataFrame, filters: dict = None) -> pd.DataFrame:
    """Apply orchestrator-style filters: date range, segment/country, tx type."""
    if not filters:
        return tx_df
    df = tx_df.copy()
    if filters.get("start_date"):
        df = df[df["date"] >= filters["start_date"]] if "date" in df.columns else df
    if filters.get("end_date"):
        df = df[df["date"] <= filters["end_date"]] if "date" in df.columns else df
    if filters.get("country"):
        df = df[df["country"] == filters["country"]]
    if filters.get("transaction_type"):
        df = df[df["transaction_type"] == filters["transaction_type"]]
    if filters.get("customer_ids"):
        df = df[df["customer_id"].isin(filters["customer_ids"])]
    return df


def run_eda(tx_df: pd.DataFrame, customers_df: pd.DataFrame = None, filters: dict = None) -> dict:
    """Main EDA Tool entry point (this is what gets exposed as a LangChain tool)."""
    scoped = apply_filters(tx_df, filters)

    result = {
        "scope": {
            "n_transactions": int(len(scoped)),
            "n_customers": int(scoped["customer_id"].nunique()),
            "filters_applied": filters or {},
        },
        "transaction_profile": _basic_profile(
            scoped[["amount", "transaction_type", "channel", "country"]]
        ),
        "baseline_behavior": _baseline_behavior(scoped),
        "distributions": _distributions(scoped),
    }
    if customers_df is not None:
        result["customer_profile"] = _basic_profile(
            customers_df[["age", "income", "country", "account_age_days", "is_foreign"]]
        )
    return result


if __name__ == "__main__":
    import json
    tx = pd.read_csv("/home/claude/aml_project/data/transactions.csv")
    cust = pd.read_csv("/home/claude/aml_project/data/customers.csv")
    report = run_eda(tx, cust)
    with open("/home/claude/aml_project/outputs/tables/eda_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(json.dumps(report, indent=2, default=str)[:2000])