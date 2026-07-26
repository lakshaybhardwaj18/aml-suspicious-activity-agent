# AI-Powered Suspicious Activity Detection (AML Agent)

An agentic system that parses natural-language analyst queries and dynamically
orchestrates a set of tools — EDA, feature engineering, anomaly detection, risk
classification, and explanation generation — to surface suspicious
transactions, explain _why_ they're suspicious, and recommend an escalation
action (monitor / review / report).

Built for **Campus Hackathon 2026, Problem Statement 1** by a team of 2 in
~22 hours.

---

## How it works

The agent does **not** run a fixed pipeline. It parses each query's intent,
filters, and target AML pattern via an LLM, then dynamically decides which
tools to invoke — some queries need the full detection stack, some need one
tool, and some need none at all.

| Query                                                    | Intent            | Tools invoked                                                                                                                                                                       |
| -------------------------------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"Find structuring patterns in the last 30 days"`        | `detect_pattern`  | feature engineering → anomaly detection → risk classification (date filter applied, EDA skipped since the pattern is already named)                                                 |
| `"Which customers made 10+ transactions under $10,000?"` | `aggregate`       | feature engineering only — answered directly via aggregation, no ML needed                                                                                                          |
| `"Is customer C00205 suspicious?"`                       | `lookup_customer` | feature engineering → anomaly detection → risk classification, scoped to that one customer                                                                                          |
| `"Which customer is the most suspicious?"`               | `rank_customers`  | full stack, aggregated up to customer level; if no specific pattern was named, the response surfaces whichever rule fired most often across the results instead of leaving it blank |
| `"who are you?"`                                         | `general`         | **zero tools** — chitchat/meta questions get a direct answer instead of running a full transaction scan                                                                             |

That last row exists because of a real bug we caught and fixed during
integration testing: the original fallback logic ran the _entire_ detection
pipeline for any unrecognized intent, including plain chitchat. `general`
queries now short-circuit before any tool is invoked.

### Components

- **Agent Orchestrator** (`agent/orchestrator.py`) — parses intent/filters/target
  pattern via an LLM (Groq), builds the dynamic execution plan, executes it
- **EDA Tool** (`tools/eda_tool.py`) — dataset/column profiling, baseline
  behavior, distributions; invoked only for broad/exploratory queries
- **Feature Engineering Tool** (`tools/feature_engineering.py`) — time-based
  rolling features (transaction frequency, rolling sums, velocity, amount
  deviation vs. the customer's own history, rapid cash-out detection),
  computed on-demand for whatever slice the orchestrator filtered to — not
  reused from any pre-baked, dataset-wide column
- **Anomaly Detection Tool** (`tools/anomaly_detection.py`) — rule-based
  detectors (structuring, smurfing, layering, unusual amount, high velocity)
  blended with an Isolation Forest ML layer into a single `final_score`
- **Risk Classification** (`_classify_risk` in `agent/orchestrator.py`) —
  buckets the blended score into low / medium / high
- **Explanation Component** (`agent/explainer.py`) — generates a
  natural-language reason per flag tied to the specific triggered rules and
  transaction details, plus the escalation recommendation

### Rule calibration

Rule thresholds were empirically calibrated against this dataset's labeled
`pattern_type` field — see [`docs/RULE_CALIBRATION.md`](docs/RULE_CALIBRATION.md)
for the full methodology. Headline numbers (rule-based detector alone, vs.
ground truth):

| Metric                                            | Value  |
| ------------------------------------------------- | ------ |
| Recall                                            | 82%    |
| Precision                                         | 47%    |
| F1                                                | 0.60   |
| Structuring / smurfing recall                     | 100%   |
| Layering / rapid movement / unusual amount recall | 60–80% |

Recall was prioritized over precision deliberately: in AML, a missed
suspicious transaction is materially costlier than an extra manual review.

**Disclosed limitation:** in this synthetic dataset, `structuring` and
`smurfing` are statistically indistinguishable at the single-transaction
level (both share an identical "just under $10k" amount signature with no
burst/frequency signal separating them). This is a property of the synthetic
generator, not the detection logic — documented in full rather than papered
over.

---

## Dataset

**Synthetically generated** — no real institution or real customer data.
Structurally modeled on the IBM AML Synthetic Transaction dataset / PaySim
schema (transaction_id, customer_id, timestamp, amount, type, counterparty,
flags), scaled to 1,000 customers / 50,000 transactions for batch analysis
within the hackathon's time constraints.

Full schema, field definitions, and profiling findings:
[`docs/SCHEMA.md`](docs/SCHEMA.md). Summary:

- **`data/customers.csv`** (1,000 rows): `customer_id`, `age`, `income`,
  `country`, `account_age_days`, `is_foreign`
- **`data/transactions.csv`** (50,000 rows): `transaction_id`, `customer_id`,
  `timestamp`, `amount`, `currency`, `transaction_type`, `counterparty_id`,
  `country`, `channel`, `is_suspicious`/`is_flagged` (ground truth,
  identical fields), `pattern_type`, plus pre-computed dataset-wide stats
  (used only for baseline EDA, never as model input — recomputing them
  per-query is exactly what the Feature Engineering Tool is for)

No real customer or institutional data is used anywhere in this project.

---

## Tech stack

- **Language:** Python 3.12
- **Data/ML:** pandas, numpy, scikit-learn (Isolation Forest)
- **LLM:** [Groq](https://groq.com/) (`llama-3.3-70b-versatile` for intent
  parsing, `llama-3.1-8b-instant` for per-flag explanations) — free tier
- **Backend:** FastAPI (`interface/api.py`)
- **Frontend:** Streamlit (`interface/streamlit_app.py`)
- **Charts/reporting:** matplotlib (`tools/reporting.py`)

---

## Setup

```bash
git clone <this-repo-url>
cd aml-suspicious-activity-agent

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Set your Groq API key (free at [console.groq.com](https://console.groq.com)):

```bash
# .env  (already gitignored — never commit this file)
GROQ_API_KEY=your-key-here
```

Confirm the dataset is in place:

```
data/
  customers.csv
  transactions.csv
```

---

## Usage

**1. Start the API** (in one terminal):

```bash
uvicorn interface.api:app --reload
```

Check it's up and the dataset loaded:

```bash
curl http://127.0.0.1:8000/health
```

**2. Start the UI** (in a second terminal):

```bash
streamlit run interface/streamlit_app.py
```

Opens at `http://localhost:8501`. Click any example query or type your own.

**Or skip the UI and call the API directly:**

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Is customer C00205 suspicious?"}'
```

### Example queries

| Query                                                  | What you'll see                                                                |
| ------------------------------------------------------ | ------------------------------------------------------------------------------ |
| `Find structuring patterns in the last 30 days`        | Flagged transactions, risk levels, per-flag explanations, escalation actions   |
| `Which customers made 10+ transactions under $10,000?` | Direct list of matching customer IDs — no ML invoked                           |
| `Is customer C00205 suspicious?`                       | That customer's flagged transactions only                                      |
| `Is customer C99999 suspicious?`                       | Clean error — customer doesn't exist                                           |
| `Which customer is the most suspicious?`               | Top-N customers ranked by max risk score, aggregated across their transactions |
| `who are you?`                                         | A direct explanation of what the agent can do — no tools run                   |

---

## Testing

```bash
# Edge cases: empty filters, single-transaction customers, zero income,
# duplicate timestamps, unknown customer IDs, etc. (8/8 passing)
python tools/test_edge_cases.py

# End-to-end orchestrator -> tools -> explainer, across several query types
python tests/test_full_chain.py
```

---

## AI assistance disclosure

Per the hackathon's disclosure requirement, the following AI assistance was
used during development:

- **Claude (Anthropic)** was used to help design and implement the Feature
  Engineering, EDA, Anomaly Detection, and Reporting tools; calibrate rule
  thresholds against the labeled dataset; write the accompanying
  documentation (`docs/SCHEMA.md`, `docs/RULE_CALIBRATION.md`); diagnose and
  fix two integration bugs (the `general`-intent fallback running the full
  pipeline, and the blank `Pattern` field for un-targeted queries); and draft
  this README.
- **Groq** (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) is used at
  runtime by the deployed agent itself for query intent parsing and
  natural-language flag explanations — this is a core part of the solution,
  not a development aid.
- All rule thresholds, architecture decisions, and final code were reviewed
  and tested by the team before inclusion.

---

## Compliance notes

- No real customer or institutional data is used anywhere in this repository.
- This is a generic banking use case; no references to any specific
  financial institution appear anywhere in this codebase.
- No production-grade infrastructure is required — this performs batch
  analysis on a sample dataset, with no database dependency.
