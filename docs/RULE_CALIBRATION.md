# Rule Calibration Notes

The rule-based Anomaly Detection Tool's thresholds were calibrated by comparing
proposed rules against this dataset's ground-truth `pattern_type` labels
(available only because this is a labeled synthetic dataset — a real
deployment would need domain expert / regulatory threshold input instead).

## Key finding
This dataset's synthetic generator encodes each suspicious pattern almost
entirely through **transaction amount and amount deviation**, not through
multi-transaction burst behavior:
- `structuring` and `smurfing` are **statistically identical** at the
  single-transaction level: both sit in an $8,000–$9,499 band (just under the
  $10k reporting threshold), with no difference in transaction frequency,
  counterparty count, or velocity vs. the clean baseline.
- `layering`, `rapid_movement`, and `unusual_amount` are best explained as
  **increasing amount/deviation tiers** (median amounts ~$14k / ~$20k / ~$34k
  respectively) rather than distinct behavioral signatures.

This is a known limitation of simplified synthetic AML datasets and is
disclosed here rather than papered over.

## What this means for the rules
- The `flag_structuring` / `flag_smurfing` rules both key off the same
  near-threshold amount band for this dataset, but each also carries a
  secondary, independent condition (burst-of-transactions crossing the
  threshold / many small transactions in 24h) that would correctly
  discriminate them on data with genuine burst behavior.
- `flag_layering` uses an amount-tier + deviation threshold calibrated
  against the empirical medians, plus behavioral fallbacks (distinct
  counterparties in 7 days, rapid cash-out).

## Calibration results (rule fires vs. true label)

| Pattern | Recall (any rule fires) |
|---|---|
| structuring | 100% |
| smurfing | 100% |
| layering | 59.5% |
| rapid_movement | 68.3% |
| unusual_amount | 79.8% |

**Overall (any-rule vs is_suspicious):** recall 82%, precision 47%, F1 0.60.

Recall was prioritized over precision deliberately — in AML, a missed
suspicious transaction (false negative) is materially costlier than an
extra manual review (false positive). The Isolation Forest ML layer runs
alongside the rules and contributes to the blended `final_score`, giving
analysts a secondary, non-rule-based signal for anything the fixed
thresholds miss.
