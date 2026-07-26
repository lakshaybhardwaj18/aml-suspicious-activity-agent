"""
Explanation Component — turns the orchestrator's output into the
final human-readable response: execution summary, flags, risk levels,
explanations, and escalation recommendation.
"""

from agent.orchestrator import ParsedQuery
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import json

EXPLAIN_PROMPT = """A transaction was flagged as suspicious.
Pattern suspected: {pattern}
Risk level: {risk_level}
Rules triggered: {triggered_rules}
Transaction details: {details}

Return JSON only, no extra text, with exactly these keys:
- explanation: 1-2 sentences explaining why THIS SPECIFIC transaction is suspicious.
  Reference the actual triggered rules and specific numbers from the transaction details
  above — do not use generic boilerplate language repeated across different transactions.
- recommended_action: one of "monitor", "review", "report"
"""

def explain_flag(row, pattern):
    from agent.orchestrator import call_llm
    prompt = EXPLAIN_PROMPT.format(
        pattern=pattern or "general anomaly",
        risk_level=row.get("risk_level", "unknown"),
        triggered_rules=row.get("triggered_rules", []),
        details=row.to_dict(),
    )
    raw = call_llm(prompt, temperature=0.6, model="llama-3.1-8b-instant")
    data = json.loads(raw)
    return {
        "explanation": data.get("explanation", ""),
        "recommended_action": data.get("recommended_action", "review"),
    }


def _explain_rows_parallel(rows: list, pattern, max_workers: int = 5) -> list[dict]:
    """Fire explain_flag() for multiple rows concurrently instead of sequentially.
    Same number of LLM calls, same quality per call — just not waiting for each
    one to finish before starting the next."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda row: explain_flag(row, pattern), rows))


def rank_customers(risk_df: pd.DataFrame, top_n: int = 5, ascending: bool = False) -> list[dict]:
    """Aggregate transaction-level risk up to customer-level, take the top/bottom N."""
    per_customer = (
        risk_df.groupby("customer_id")
        .agg(max_risk_score=("risk_score", "max"), flagged_tx_count=("risk_score", "count"))
        .sort_values("max_risk_score", ascending=ascending)
        .head(top_n)
    )

    worst_rows = [
        risk_df[risk_df["customer_id"] == cust_id]
        .sort_values("risk_score", ascending=ascending).iloc[0]
        for cust_id in per_customer.index
    ]
    explanations = _explain_rows_parallel(worst_rows, None)

    results = []
    for (cust_id, row), explanation in zip(per_customer.iterrows(), explanations):
        results.append({
            "customer_id": cust_id,
            "max_risk_score": row["max_risk_score"],
            "flagged_transaction_count": int(row["flagged_tx_count"]),
            "explanation": explanation["explanation"],
            "recommended_action": explanation["recommended_action"],
        })
    return results


def answer_aggregate_query(features_df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    df = features_df.copy()

    if parsed.min_transaction_count is not None and "tx_count_total" in df.columns:
        df = df[df["tx_count_total"] >= parsed.min_transaction_count]

    if parsed.amount_threshold is not None and "avg_amount" in df.columns:
        df = df[df["avg_amount"] < parsed.amount_threshold]

    matching_customers = df["customer_id"].unique().tolist() if "customer_id" in df.columns else []
    return {"matching_customers": matching_customers, "count": len(matching_customers)}


def build_response(context: dict) -> dict:
    if "error" in context:
        return {"error": context["error"]}

    parsed: ParsedQuery = context["parsed_query"]
    execution_summary = {
        "query_intent": parsed.intent,
        "detected_pattern": parsed.target_pattern,
        "filters_applied": parsed.filters,
        "tools_invoked": context["plan_used"],
    }

    flagged_items = []
    aggregate_result = None
    ranked_customers = None
    note=None
    if parsed.intent == "rank_customers" and "risk_df" in context:
        MAX_RANKED_CUSTOMERS = 25
        ascending = parsed.sort_direction == "asc"
        if parsed.requested_count and parsed.requested_count > MAX_RANKED_CUSTOMERS:
            actual_count = MAX_RANKED_CUSTOMERS
            note = f"Showing {MAX_RANKED_CUSTOMERS} (capped for response time; you asked for {parsed.requested_count})"
        else:
            actual_count = parsed.requested_count or 5
        ranked_customers = rank_customers(context["risk_df"], top_n=actual_count, ascending=ascending)
        ranked_label = "Least Suspicious Customers" if ascending else "Most Suspicious Customers"
    elif "risk_df" in context:
        top_flags = context["risk_df"].sort_values("risk_score", ascending=False).head(10)
        rows = [row for _, row in top_flags.iterrows()]
        explanations = _explain_rows_parallel(rows, parsed.target_pattern)
        for row, explanation in zip(rows, explanations):
            flagged_items.append({
                "id": row.get("customer_id") or row.get("transaction_id"),
                "risk_score": row.get("risk_score"),
                "risk_level": row.get("risk_level"),
                "explanation": explanation["explanation"],
                "ranked_label": ranked_label if ranked_customers else None,
                "recommended_action": explanation["recommended_action"],
            })
    elif parsed.intent == "aggregate" and "features_df" in context:
        aggregate_result = answer_aggregate_query(context["features_df"], parsed)
    return {
        "execution_summary": execution_summary,
        "flagged_items": flagged_items,
        "aggregate_result": aggregate_result,
        "ranked_customers": ranked_customers,
        "note": note,
    }