"""
Temporary fake tools — matches the real contract Member 2 is building.
Delete this once tools/ is actually implemented.
"""
import pandas as pd

def fake_run_eda(df, filters):
    return {"row_count": len(df), "columns": list(df.columns)}

def fake_engineer_features(df, filters, pattern):
    # Real transactions.csv already has most features baked in —
    # this just simulates returning that same shape
    return df.copy()

def fake_detect_anomalies(df, pattern):
    out = df.copy()
    out["risk_score"] = out["amount_deviation"].fillna(0) if "amount_deviation" in out.columns else 0.5
    return out

def fake_classify_risk(df):
    out = df.copy()
    out["risk_level"] = out["risk_score"].apply(
        lambda s: "high" if s > 1.5 else "medium" if s > 0.8 else "low"
    )
    return out