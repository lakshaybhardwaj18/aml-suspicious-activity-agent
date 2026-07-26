"""
Edge-case tests for the data pipeline / feature engineering / anomaly
detection tools, run before the Hour 9 and Hour 14-17 integration syncs
with Member 1's orchestrator. Each test simulates a scenario the
orchestrator's dynamic filtering could realistically produce.
"""
import sys
sys.path.insert(0, "/home/claude/aml_project/tools")
import pandas as pd
import numpy as np
from feature_engineering import engineer_features
from anomaly_detection import detect_anomalies
from eda_tool import run_eda, apply_filters

tx = pd.read_csv("/home/claude/aml_project/data/transactions.csv")
cust = pd.read_csv("/home/claude/aml_project/data/customers.csv")

results = []

def check(name, fn):
    try:
        fn()
        results.append((name, "PASS", ""))
    except Exception as e:
        results.append((name, "FAIL", str(e)))

# 1. Empty result set (filter that matches nothing) -> orchestrator could
#    easily construct a query like this (typo'd country, future date range)
def t1():
    empty = tx[tx["country"] == "Nowhere"]
    feat = engineer_features(empty, cust)
    assert len(feat) == 0
    scored = detect_anomalies(feat, use_ml=False)  # use_ml=False: IsolationForest needs >0 rows
    assert len(scored) == 0
check("empty_filtered_dataset", t1)

# 2. Single-transaction customer (expanding std is NaN by definition -> must
#    not crash, and amount_deviation should safely become 0, not NaN/inf)
def t2():
    single = tx[tx["customer_id"] == tx["customer_id"].iloc[0]].head(1)
    feat = engineer_features(single, cust)
    assert not feat["amount_deviation"].isna().any()
    assert np.isfinite(feat["amount_deviation"]).all()
check("single_transaction_customer", t2)

# 3. Single-customer, single-country date-range slice (typical orchestrator query)
def t3():
    sliced = apply_filters(tx, {"country": "Singapore"})
    feat = engineer_features(sliced, cust)
    scored = detect_anomalies(feat, use_ml=True)
    assert "final_score" in scored.columns
    assert scored["final_score"].between(0, 1.5).all()  # allow slight >1 from blended weights
check("country_filtered_slice", t3)

# 4. All-clean segment (no suspicious transactions at all) -> Isolation
#    Forest contamination=0.2 default could misbehave if true rate is 0
def t4():
    clean_only = tx[tx["is_suspicious"] == False].head(500)
    feat = engineer_features(clean_only, cust)
    scored = detect_anomalies(feat, use_ml=True)
    assert scored["ml_score"].between(0, 1).all()
check("all_clean_segment_ml_scoring", t4)

# 5. Zero / missing income (division by zero in amount_to_income_ratio)
def t5():
    bad_cust = cust.copy()
    bad_cust.loc[0, "income"] = 0
    sample = tx[tx["customer_id"] == bad_cust.loc[0, "customer_id"]]
    feat = engineer_features(sample, bad_cust)
    assert np.isfinite(feat["amount_to_income_ratio"].replace([np.inf, -np.inf], np.nan).dropna()).all()
check("zero_income_division_safety", t5)

# 6. Duplicate timestamps for the same customer (two transactions in the
#    same second -- rolling window must not crash on non-unique index)
def t6():
    dup = tx[tx["customer_id"] == tx["customer_id"].iloc[0]].head(2).copy()
    dup["timestamp"] = dup["timestamp"].iloc[0]  # force identical timestamps
    feat = engineer_features(dup, cust)
    assert len(feat) == 2
check("duplicate_timestamps_same_customer", t6)

# 7. Extreme outlier amount (near dataset max, ~470k) shouldn't blow up scoring
def t7():
    outlier = tx.nlargest(5, "amount")
    feat = engineer_features(outlier, cust)
    scored = detect_anomalies(feat, use_ml=False)
    assert scored["final_score"].notna().all()
check("extreme_outlier_amount", t7)

# 8. Missing/unknown customer_id in transactions (orchestrator passes a
#    customer not in customers.csv -- merge should not silently drop rows)
def t8():
    fake = tx.head(3).copy()
    fake["customer_id"] = "C_UNKNOWN"
    feat = engineer_features(fake, cust)
    assert len(feat) == 3  # left-merge must preserve all transaction rows
check("unknown_customer_id_left_merge", t8)

print(f"{'TEST':40s} {'RESULT':6s} DETAIL")
for name, status, detail in results:
    print(f"{name:40s} {status:6s} {detail}")

n_pass = sum(1 for _, s, _ in results if s == "PASS")
print(f"\n{n_pass}/{len(results)} passed")
