# Dataset Schema

Two files, joined on `customer_id`.

## customers.csv (1,000 rows)

| Column | Type | Description |
|---|---|---|
| customer_id | string | Unique customer identifier (C00001 ...) |
| age | int | Customer age |
| income | float | Annual income (USD) |
| country | category (5) | UK, India, UAE, USA, Singapore |
| account_age_days | int | Days since account opened |
| is_foreign | binary | 1 = foreign national |

## transactions.csv (50,000 rows)

| Column | Type | Description |
|---|---|---|
| transaction_id | string | Unique transaction id |
| customer_id | string | FK -> customers.csv |
| timestamp | datetime | Transaction timestamp |
| amount | float | Transaction amount (USD) |
| currency | category | Always USD in this sample |
| transaction_type | category (4) | Payment, Deposit, Withdrawal, Transfer |
| counterparty_id | string | Other party in the transaction (500 unique) |
| country | category (5) | Transaction country |
| channel | category (4) | Mobile, ATM, Online, Branch |
| is_suspicious / is_flagged | bool | **Ground-truth label** (identical fields — treat as one target) |
| pattern_type | category (5) + NaN | smurfing / rapid_movement / unusual_amount / layering / structuring (NaN when not suspicious) |
| tx_count_total, tx_count_daily, total_amount, avg_amount, amount_deviation, unique_counterparties, tx_count_7d, tx_count_24h, hour, day_of_week, is_weekend, tx_type_encoded, channel_encoded, date | various | **Pre-computed, dataset-wide** stats. Useful for baseline EDA, but NOT used directly as agent-facing features since they're computed over the *entire* history, not the *query-filtered* slice. The Feature Engineering Tool recomputes equivalents on demand for whatever subset the orchestrator passes in. |

## Key facts from profiling
- No missing values except `pattern_type` (expected — NaN for non-suspicious transactions).
- `is_suspicious` and `is_flagged` are 100% identical -> one label, not two independent signals. Never fed as a model input (would leak the answer).
- Base rate: ~20% of transactions are suspicious, evenly spread across the 5 pattern types (~2,000 each).
- Full calendar year 2024, single currency (USD), 5 countries, balanced categories -> good for slicing by segment/country/date range as the orchestrator requires.

## Data source / citation (for README)
Synthetic dataset generated for this hackathon — structurally modeled on the IBM AML Synthetic Transaction dataset / PaySim schema (transaction_id, customer_id, timestamp, amount, type, counterparty, flags), scaled down to 1,000 customers / 50,000 transactions for batch analysis. No real customer data is used.
