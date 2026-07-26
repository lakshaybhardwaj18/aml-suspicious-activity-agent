"""
Anomaly Detection Tool
------------------------
Scores suspicious transactions/customers using rule-based thresholds first
(structuring, smurfing, layering / rapid movement, unusual amount), with an
optional Isolation Forest layer to catch anything the rules miss.

Requires the output of feature_engineering.engineer_features() as input.

Public entry point: detect_anomalies(feat_df, use_ml=True) -> pd.DataFrame
    adds: rule_flags (dict per row), rule_score, ml_score, final_score
"""

import pandas as pd
import numpy as np

# ---- Thresholds -------------------------------------------------------
# Calibrated empirically against this dataset's labeled pattern_type
# (see docs/RULE_CALIBRATION.md). Two notes:
#  1. In this synthetic generator, `structuring` and `smurfing` share an
#     IDENTICAL single-transaction signature (amount just under the $10k
#     reporting threshold) -- there's no burst/frequency signal separating
#     them in the data, so both rules key off the same amount band. A real
#     deployment would additionally need true multi-transaction burst
#     detection to tell them apart (kept below as a secondary signal so
#     the rule still behaves correctly on real burst behavior).
#  2. `layering`, `rapid_movement`, `unusual_amount` are best explained as
#     increasing amount/deviation TIERS rather than distinct behavioral
#     signatures in this dataset, so thresholds are tiered accordingly.
STRUCTURING_THRESHOLD = 10000         # classic reporting threshold
STRUCTURING_LOWER_BOUND = 8000        # "just under" band lower edge (empirical)
SMURFING_MIN_TX_24H = 4               # secondary signal: many small tx in short window
SMURFING_MAX_AVG_AMOUNT = 2000        # ... each individually small
LAYERING_MIN_AMOUNT = 10000           # layering/rapid-movement tier starts above threshold
LAYERING_MIN_DEVIATION = 0.3          # ... and noticeably above the customer's own baseline
LAYERING_MIN_COUNTERPARTIES_7D = 5    # secondary signal: many distinct counterparties fast
UNUSUAL_AMOUNT_ZSCORE = 2.0           # amount far from customer's own baseline
VELOCITY_HIGH_PCTL = 0.99             # top 1% of money-velocity flagged


def _flag_structuring(df: pd.DataFrame) -> pd.Series:
    """Single transaction just under the reporting threshold (empirically the
    primary signature in this dataset), OR a burst of transactions whose
    rolling sum crosses the threshold even though no single one does
    (the classic multi-transaction structuring pattern for real data)."""
    near_threshold = (
        (df["amount"] < STRUCTURING_THRESHOLD) &
        (df["amount"] >= STRUCTURING_LOWER_BOUND)
    )
    burst_crosses_threshold = (
        (df["rolling_sum_24h"] >= STRUCTURING_THRESHOLD) &
        (df["tx_count_24h"] >= 2) &
        (df["amount"] < STRUCTURING_THRESHOLD)
    )
    return near_threshold | burst_crosses_threshold


def _flag_smurfing(df: pd.DataFrame) -> pd.Series:
    """Smurfing: many small transactions in a short window (true burst
    signature), OR the same near-threshold amount band as structuring --
    in this dataset the two labels are empirically indistinguishable at
    the single-transaction level, so this rule intentionally overlaps with
    _flag_structuring. The tx-count/small-amount branch is the real
    discriminator that would apply once genuine burst behavior is present."""
    burst_small_amounts = (
        (df["tx_count_24h"] >= SMURFING_MIN_TX_24H) &
        (df["amount"] <= SMURFING_MAX_AVG_AMOUNT)
    )
    near_threshold = (
        (df["amount"] < STRUCTURING_THRESHOLD) &
        (df["amount"] >= STRUCTURING_LOWER_BOUND)
    )
    return burst_small_amounts | near_threshold


def _flag_layering(df: pd.DataFrame) -> pd.Series:
    """Layering / rapid fund movement: amount clearly above the reporting
    threshold AND noticeably above the customer's own historical baseline
    (empirically the dominant signal for layering/rapid_movement in this
    dataset), OR the classic behavioral signals -- many distinct
    counterparties in a short window, or a deposit immediately followed by
    an outbound move (rapid cash-out)."""
    amount_tier = (
        (df["amount"] >= LAYERING_MIN_AMOUNT) &
        (df["amount_deviation"] >= LAYERING_MIN_DEVIATION)
    )
    many_counterparties = df.get("unique_counterparties_7d", 0) >= LAYERING_MIN_COUNTERPARTIES_7D
    rapid_cashout = df.get("rapid_cashout_flag", False) == True
    return amount_tier | many_counterparties | rapid_cashout


def _flag_unusual_amount(df: pd.DataFrame) -> pd.Series:
    """Amount far from the customer's own historical average (self-referential
    z-score, computed with no look-ahead in feature_engineering.py)."""
    return df["amount_deviation"].abs() >= UNUSUAL_AMOUNT_ZSCORE


def _flag_high_velocity(df: pd.DataFrame) -> pd.Series:
    """Money moving unusually fast (top percentile of $/hour over trailing 24h)."""
    if "velocity_24h" not in df.columns or df["velocity_24h"].isna().all():
        return pd.Series(False, index=df.index)
    threshold = df["velocity_24h"].quantile(VELOCITY_HIGH_PCTL)
    return df["velocity_24h"] >= threshold


def apply_rules(feat_df: pd.DataFrame) -> pd.DataFrame:
    """Applies all rule-based detectors and produces a rule_score (0-5) plus
    a human-readable list of triggered rules per row (feeds the Explanation
    Component directly)."""
    df = feat_df.copy()

    df["flag_structuring"] = _flag_structuring(df)
    df["flag_smurfing"] = _flag_smurfing(df)
    df["flag_layering"] = _flag_layering(df)
    df["flag_unusual_amount"] = _flag_unusual_amount(df)
    df["flag_high_velocity"] = _flag_high_velocity(df)

    rule_cols = ["flag_structuring", "flag_smurfing", "flag_layering",
                 "flag_unusual_amount", "flag_high_velocity"]
    df["rule_score"] = df[rule_cols].sum(axis=1)

    def _triggered(row):
        return [c.replace("flag_", "") for c in rule_cols if row[c]]
    df["triggered_rules"] = df[rule_cols].apply(
        lambda row: [c.replace("flag_", "") for c in rule_cols if row[c]], axis=1
    )
    return df


def apply_isolation_forest(df: pd.DataFrame, contamination: float = 0.2) -> pd.DataFrame:
    """ML layer: Isolation Forest over the engineered numeric features, to
    catch multivariate anomalies the fixed rules miss. contamination is set
    to match the dataset's known ~20% suspicious rate (tunable in prod)."""
    from sklearn.ensemble import IsolationForest

    ml_features = ["amount", "tx_count_24h", "tx_count_7d", "rolling_sum_24h",
                   "velocity_24h", "amount_deviation"]
    ml_features = [c for c in ml_features if c in df.columns]

    X = df[ml_features].fillna(0)
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
    model.fit(X)
    # decision_function: lower = more anomalous. Flip sign so higher = more suspicious.
    raw_scores = -model.decision_function(X)
    # normalize to 0-1
    df["ml_score"] = (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min())
    df["ml_flag"] = model.predict(X) == -1
    return df


def detect_anomalies(feat_df: pd.DataFrame, use_ml: bool = True) -> pd.DataFrame:
    """Main Anomaly Detection Tool entry point."""
    df = apply_rules(feat_df)

    if use_ml:
        df = apply_isolation_forest(df)
        # blended score: rules are authoritative (interpretable), ML adds a
        # confidence boost when it agrees, and can surface rule-missed cases
        df["final_score"] = (df["rule_score"] / 5.0) * 0.7 + df["ml_score"] * 0.3
    else:
        df["ml_score"] = np.nan
        df["ml_flag"] = False
        df["final_score"] = df["rule_score"] / 5.0

    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/claude/aml_project/tools")
    from feature_engineering import engineer_features

    tx = pd.read_csv("/home/claude/aml_project/data/transactions.csv")
    cust = pd.read_csv("/home/claude/aml_project/data/customers.csv")

    print("Engineering features on FULL dataset (this validates end-to-end)...")
    feat = engineer_features(tx, cust, compute_rapid_cashout=True)
    feat.to_csv("/home/claude/aml_project/outputs/tables/features_full.csv", index=False)

    print("Running anomaly detection (rules + Isolation Forest)...")
    scored = detect_anomalies(feat, use_ml=True)
    scored.to_csv("/home/claude/aml_project/outputs/tables/scored_transactions.csv", index=False)

    # ---- Validation against ground truth (available only because this is
    # a labeled synthetic dataset -- won't exist in a real deployment) ----
    scored["predicted_suspicious"] = scored["rule_score"] >= 1
    from sklearn.metrics import classification_report, confusion_matrix
    print("\n=== Rule-based detector vs ground truth (is_suspicious) ===")
    print(confusion_matrix(scored["is_suspicious"], scored["predicted_suspicious"]))
    print(classification_report(scored["is_suspicious"], scored["predicted_suspicious"]))

    print("\n=== Isolation Forest (ml_flag) vs ground truth ===")
    print(confusion_matrix(scored["is_suspicious"], scored["ml_flag"]))
    print(classification_report(scored["is_suspicious"], scored["ml_flag"]))

    print("\nSaved: outputs/tables/features_full.csv, outputs/tables/scored_transactions.csv")
