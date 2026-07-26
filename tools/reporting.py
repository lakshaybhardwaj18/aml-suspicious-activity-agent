"""
Reporting: charts + tables consumed by the interface / README / deck.
Run after anomaly_detection.py has produced outputs/tables/scored_transactions.csv
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_CHARTS = "/home/claude/aml_project/outputs/charts"
OUT_TABLES = "/home/claude/aml_project/outputs/tables"

df = pd.read_csv(f"{OUT_TABLES}/scored_transactions.csv")

# ---- Chart 1: flagged transaction distribution by pattern type ----
plt.figure(figsize=(7, 4.5))
counts = df[df["is_suspicious"]]["pattern_type"].value_counts()
plt.bar(counts.index, counts.values, color="#c0392b")
plt.title("Flagged Transactions by Pattern Type")
plt.ylabel("Count")
plt.xticks(rotation=20)
plt.tight_layout()
plt.savefig(f"{OUT_CHARTS}/flagged_by_pattern.png", dpi=150)
plt.close()

# ---- Chart 2: risk breakdown (final_score binned to low/medium/high) ----
def risk_bucket(s):
    if s >= 0.5:
        return "high"
    elif s >= 0.25:
        return "medium"
    return "low"

df["risk_level"] = df["final_score"].apply(risk_bucket)
plt.figure(figsize=(6, 4.5))
risk_counts = df["risk_level"].value_counts().reindex(["low", "medium", "high"])
plt.bar(risk_counts.index, risk_counts.values, color=["#27ae60", "#f39c12", "#c0392b"])
plt.title("Risk Level Breakdown (All Transactions)")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(f"{OUT_CHARTS}/risk_breakdown.png", dpi=150)
plt.close()

# ---- Chart 3: rule hit-rate vs ground truth pattern (calibration chart) ----
patterns = ["structuring", "smurfing", "layering", "rapid_movement", "unusual_amount"]
hit_rates = [df[df["pattern_type"] == p]["rule_score"].gt(0).mean() * 100 for p in patterns]
plt.figure(figsize=(7, 4.5))
plt.bar(patterns, hit_rates, color="#2980b9")
plt.axhline(50, color="gray", linestyle="--", linewidth=1)
plt.title("Rule-Based Detection Recall by True Pattern Type")
plt.ylabel("% Correctly Flagged")
plt.xticks(rotation=20)
plt.tight_layout()
plt.savefig(f"{OUT_CHARTS}/rule_recall_by_pattern.png", dpi=150)
plt.close()

# ---- Chart 4: amount distribution, suspicious vs clean ----
plt.figure(figsize=(7, 4.5))
plt.hist(df[~df["is_suspicious"]]["amount"].clip(upper=50000), bins=50, alpha=0.6, label="Clean", color="#27ae60")
plt.hist(df[df["is_suspicious"]]["amount"].clip(upper=50000), bins=50, alpha=0.6, label="Suspicious", color="#c0392b")
plt.title("Transaction Amount Distribution: Clean vs Suspicious")
plt.xlabel("Amount (USD, clipped at 50k)")
plt.ylabel("Count")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUT_CHARTS}/amount_distribution.png", dpi=150)
plt.close()

# ---- Table: risk breakdown by segment (country) ----
risk_by_country = (
    df.groupby(["country", "risk_level"]).size().unstack(fill_value=0)
    .reindex(columns=["low", "medium", "high"], fill_value=0)
)
risk_by_country.to_csv(f"{OUT_TABLES}/risk_by_country.csv")

# ---- Table: top 25 highest-risk flagged transactions (for demo/README) ----
top_flagged = df[df["is_suspicious"]].nlargest(25, "final_score")[
    ["transaction_id", "customer_id", "amount", "transaction_type", "country",
     "pattern_type", "triggered_rules", "rule_score", "ml_score", "final_score", "risk_level"]
]
top_flagged.to_csv(f"{OUT_TABLES}/top_25_flagged.csv", index=False)

# ---- Summary table: model performance ----
from sklearn.metrics import precision_score, recall_score, f1_score
df["predicted_suspicious"] = df["rule_score"] >= 1
summary = pd.DataFrame([{
    "detector": "rule_based",
    "precision": round(precision_score(df["is_suspicious"], df["predicted_suspicious"]), 3),
    "recall": round(recall_score(df["is_suspicious"], df["predicted_suspicious"]), 3),
    "f1": round(f1_score(df["is_suspicious"], df["predicted_suspicious"]), 3),
}, {
    "detector": "isolation_forest",
    "precision": round(precision_score(df["is_suspicious"], df["ml_flag"]), 3),
    "recall": round(recall_score(df["is_suspicious"], df["ml_flag"]), 3),
    "f1": round(f1_score(df["is_suspicious"], df["ml_flag"]), 3),
}])
summary.to_csv(f"{OUT_TABLES}/model_performance_summary.csv", index=False)

print("Charts saved to", OUT_CHARTS)
print("Tables saved to", OUT_TABLES)
print()
print(summary)
