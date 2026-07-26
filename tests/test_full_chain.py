# tests/test_full_chain.py
import pandas as pd
from unittest.mock import patch
from agent.orchestrator import handle_query
from tests.fake_tools import (
    fake_run_eda, fake_engineer_features, fake_detect_anomalies, fake_classify_risk
)

df = pd.read_csv("data/transactions.csv")

with patch("tools.eda.run_eda", fake_run_eda), \
     patch("tools.feature_engineering.engineer_features", fake_engineer_features), \
     patch("tools.anomaly_detection.detect_anomalies", fake_detect_anomalies), \
     patch("tools.risk_classification.classify_risk", fake_classify_risk):

    for q in [
        "Find structuring patterns in the last 30 days",
        "Which customers made 10+ transactions under $10,000?",
        "Is customer C00205 suspicious?",
        "Is customer C99999 suspicious?",
    ]:
        result = handle_query(q, df)
        print(q)
        print(result)
        print("---")