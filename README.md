# AI-Powered Suspicious Activity Detection (AML Agent)

An agentic system that parses natural-language analyst queries and dynamically
orchestrates a set of tools — EDA, feature engineering, anomaly detection, risk
classification, and explanation generation — to surface suspicious transactions,
explain *why* they're suspicious, and recommend an escalation action.

Built for Campus Hackathon 2026, Problem Statement 1.

## How it works

The agent does **not** run a fixed pipeline. It parses each query's intent,
filters, and target AML pattern, then decides which tools to invoke:

| Query | What the agent does |
|---|---|
| `"Find structuring patterns in the last 30 days"` | Applies the date filter, skips EDA, runs feature engineering → anomaly detection → risk classification |
| `"Which customers made 10+ transactions under $10,000?"` | Runs feature engineering only, answers directly via aggregation — no ML needed |
| `"Is customer C00205 suspicious?"` | Scopes to that one customer, runs the full detection flow, returns their flagged transactions with explanations |

**Components:**
- **Agent Orchestrator** (`agent/orchestrator.py`) — parses intent via an LLM (Groq), builds a dynamic execution plan
- **EDA Tool** (`tools/eda_tool.py`) — dataset/column profiling, baseline behavior, distributions
- **Feature Engineering Tool** (`tools/feature_engineering.py`) — time-based rolling features (transaction frequency, velocity, amount deviation, rapid cash-out) computed on-demand for the query-filtered slice
- **Anomaly Detection Tool** (`tools/anomaly_detection.py`) — rule-based detectors (structuring, smurfing, layering, unusual amount, high velocity) blended with an Isolation Forest ML layer
- **Risk Classification** (in `agent/orchestrator.py`) — buckets the blended score into low/medium/high
- **Explanation Component** (`agent/explainer.py`) — generates a natural-language reason per flag, tied to the query intent and detected pattern, plus an escalation recommendation (monitor/review/report)

Rule thresholds were empirically calibrated against this dataset's labeled
patterns — see `docs/RULE_CALIBRATION.md` for the full methodology, including
a disclosed limitation (structuring and smurfing are statistically
indistinguishable at the single-transaction level in this synthetic
generator) and calibration results (82% recall, 47% precision on rule-based
detection alone).

## Dataset

**Synthetically generated** — not sourced from a real institution or real
customer data. Structurally modeled on the IBM AML Synthetic Transaction
dataset / PaySim schema (transaction_id, customer_id, timestamp, amount,
type, counterparty, flags), scaled down to 1,000 customers / 50,000
transactions for batch analysis within the hackathon's time constraints.

Full schema, field definitions, and generation assumptions are documented in
`docs/SCHEMA.md`. Summary:

- `data/customers.csv` — 1,000 rows: customer_id, age, income, country, account_age_days, is_foreign
- `data/transactions.csv` — 50,000 rows: transaction_id, customer_id, timestamp, amount, currency, transaction_type, counterparty_id, country, channel, is_suspicious/is_flagged (ground truth), pattern_type, plus pre-computed dataset-wide stats used for baseline EDA only

No real customer or institutional data is used anywhere in this project.

## Tech Stack

- **Python** — pandas, numpy, scikit-learn (Isolation Forest)
- **LLM**: [Groq](https://groq.com/) (`llama-3.3-70b-versatile`) — free tier, used for query intent parsing and explanation generation
- - **Interface**: FastAPI backend (`interface/api.py`) + Streamlit frontend (`interface/streamlit_app.py`)
- **Charts/reporting**: matplotlib (`tools/reporting.py`)

## Setup

```bash
git clone <this-repo-url>
cd aml-suspicious-activity-agent
pip install -r requirements.txt
```

Set your Groq API key (get one free at console.groq.com):

```bash
# .env file (not committed — see .gitignore)
GROQ_API_KEY=your-key-here
```

Place the dataset files:
```
data/
  customers.csv
  transactions.csv
```

## Usage

**Run the API:**
```bash
uvicorn interface.api:app --reload
```
Visit `http://127.0.0.1:8000/docs` for the interactive Swagger UI, or POST directly:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Is customer C00205 suspicious?"}'
```

**Example queries and expected behavior:**

1. `"Find structuring patterns in the last 30 days"` → returns top flagged transactions with risk scores, explanations, and escalation actions
2. `"Which customers made 10+ transactions under $10,000?"` → returns a direct list of matching customer IDs, no ML invoked
3. `"Is customer C00205 suspicious?"` → returns that customer's flagged transactions only
4. `"Is customer C99999 suspicious?"` → returns a clean error for a non-existent customer

**Run the offline batch scoring + chart generation** (produces the charts/tables used in the deck and this README):
```bash
python tools/anomaly_detection.py   # scores the full dataset
python tools/reporting.py            # generates charts + summary tables
```

## Model Performance

See `docs/RULE_CALIBRATION.md` and `outputs/tables/model_performance_summary.csv`
for full precision/recall/F1 by detector. Recall was prioritized over precision
deliberately — in AML, a missed suspicious transaction is materially costlier
than an extra manual review.

## External Tools, APIs & AI Assistance Disclosed

- **Groq API** (free tier) — LLM inference for query parsing and explanation generation
- **scikit-learn** — Isolation Forest for ML-based anomaly detection
- **Claude (Anthropic)** — used for development assistance (code review, debugging, architecture planning) during the hackathon
- No proprietary, confidential, or copyrighted data sources used

## Team

- **Lakshay Bhardwaj** — Agent orchestration, explanation component, interface, integration
- **Sharan Sansanwal** — Dataset generation, EDA, feature engineering, anomaly detection, reporting