# AI-Powered Suspicious Activity Detection (AML Agent)

Campus Hackathon 2026, Problem Statement 1. Built by a team of 2 in ~22 hours.

An agent that takes a natural-language query, figures out what you're
actually asking, and only runs the tools it needs to answer it — instead of
running one fixed pipeline every time.

## Components

- `agent/orchestrator.py` — parses intent/filters/pattern via an LLM (Groq),
  decides which tools to run, executes them
- `tools/eda_tool.py` — dataset profiling, distributions, baseline behavior
- `tools/feature_engineering.py` — rolling transaction frequency, velocity,
  amount deviation, rapid cash-out detection, computed on the fly for
  whatever slice of data the query is scoped to
- `tools/anomaly_detection.py` — rule-based detection (structuring, smurfing,
  layering, unusual amount, high velocity) blended with an Isolation Forest
- `_classify_risk()` in `orchestrator.py` — buckets the score into low/medium/high
- `agent/explainer.py` — writes the natural-language explanation per flag and
  the escalation call (monitor / review / report)

## Dynamic planning, with examples

- "Find structuring patterns in the last 30 days" → feature engineering →
  anomaly detection → risk classification
- "Which customers made 10+ transactions under $10,000?" → feature
  engineering only, answered by aggregation, no ML
- "Is customer C00205 suspicious?" → same 3 tools, scoped to that customer
- "Which customer is the most suspicious?" → full stack, aggregated to
  customer level. If no pattern was named in the query, it reports whichever
  rule fired most often across the results instead of leaving it blank
- "who are you?" → no tools at all, just answers directly

That last case matters because it used to be a bug: anything that wasn't an
explicit AML query fell through to "run everything," so asking the agent a
random question would trigger a full 50k-row analysis. Fixed now.

## Rule calibration

Thresholds were tuned against this dataset's labeled `pattern_type` field —
details in `docs/RULE_CALIBRATION.md`. Rule-based detector alone: 82% recall,
47% precision, F1 0.60. Recall matters more than precision here since missing
a suspicious transaction is worse than an extra manual review.

One thing worth flagging: in this synthetic dataset, `structuring` and
`smurfing` look identical at the single-transaction level (same "just under
$10k" amount band, no burst signal separating them). That's a property of
the generator, not something the rules are getting wrong.

## Dataset

Synthetic, not real customer data. Same shape as IBM's AML Synthetic
Transaction dataset / PaySim (transaction_id, customer_id, timestamp, amount,
type, counterparty, flags), scaled to 1,000 customers / 50,000 transactions.
Full schema in `docs/SCHEMA.md`.

## Tech stack

Python, pandas/numpy/scikit-learn, Groq (`llama-3.3-70b-versatile` for intent
parsing, `llama-3.1-8b-instant` for explanations), FastAPI backend, Streamlit
frontend.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Add a `.env` file with:

```
GROQ_API_KEY=your-key-here
```

Make sure `data/customers.csv` and `data/transactions.csv` are in place.

## Running it

```bash
uvicorn interface.api:app --reload
```

and in a second terminal:

```bash
streamlit run interface/streamlit_app.py
```

Or hit the API directly:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Is customer C00205 suspicious?"}'
```

## Testing

```bash
python tools/test_edge_cases.py
python tests/test_full_chain.py
```

## AI assistance disclosure

Claude (Anthropic) was used to help build the tools, calibrate the rule
thresholds, debug the two issues mentioned above, and write this README.
Groq is used at runtime by the agent itself for intent parsing and
explanations — that's part of the actual solution, not a dev-time aid.

## Notes

No real customer or institutional data anywhere in this repo. Generic
banking use case, no references to any specific institution. No database or
production infra required — batch analysis on a sample dataset.
