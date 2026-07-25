"""
Explanation Component — turns the orchestrator's output into the
final human-readable response: execution summary, flags, risk levels,
explanations, and escalation recommendation.
"""

from agent.orchestrator import ParsedQuery
import pandas as pd

import json

EXPLAIN_PROMPT = """A transaction was flagged as suspicious.
Pattern suspected: {pattern}
Risk level: {risk_level}
Transaction details: {details}

Return JSON only, no extra text, with exactly these keys:
- explanation: 1-2 sentences in plain language explaining why this looks suspicious, tied to the {pattern} pattern
- recommended_action: one of "monitor", "review", "report"
"""


def explain_flag(row: pd.Series, pattern: str) -> dict:
    """Generate an explanation + escalation action for a single flagged row."""
    from agent.orchestrator import call_llm

    prompt = EXPLAIN_PROMPT.format(
        pattern=pattern or "general anomaly",
        risk_level=row.get("risk_level", "unknown"),
        details=row.to_dict(),
    )
    raw = call_llm(prompt)
    data = json.loads(raw)
    return {
        "explanation": data.get("explanation", ""),
        "recommended_action": data.get("recommended_action", "review"),
    }
def answer_aggregate_query(features_df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    """
    Filter features_df by the numeric thresholds extracted from the query
    and return matching customers. Straight pandas filtering — no LLM needed
    for a pure counting/threshold question.
    """
    df = features_df.copy()

    if parsed.min_transaction_count is not None and "transaction_count" in df.columns:
        df = df[df["transaction_count"] >= parsed.min_transaction_count]

    if parsed.amount_threshold is not None and "avg_transaction_amount" in df.columns:
        df = df[df["avg_transaction_amount"] < parsed.amount_threshold]

    matching_customers = (
        df["customer_id"].tolist() if "customer_id" in df.columns else df.index.tolist()
    )
    return {"matching_customers": matching_customers, "count": len(matching_customers)}
def build_response(context: dict) -> dict:
    parsed: ParsedQuery = context["parsed_query"]

    execution_summary = {
        "query_intent": parsed.intent,
        "detected_pattern": parsed.target_pattern,
        "filters_applied": parsed.filters,
        "tools_invoked": context["plan_used"],
    }

    flagged_items = []
    aggregate_result = None

    if "risk_df" in context:
        top_flags = context["risk_df"].sort_values("risk_score", ascending=False).head(10)
        for _, row in top_flags.iterrows():
            explanation = explain_flag(row, parsed.target_pattern)
            flagged_items.append({
                "id": row.get("customer_id") or row.get("transaction_id"),
                "risk_score": row.get("risk_score"),
                "risk_level": row.get("risk_level"),
                "explanation": explanation["explanation"],
                "recommended_action": explanation["recommended_action"],
            })
    elif parsed.intent == "aggregate" and "features_df" in context:
        aggregate_result = answer_aggregate_query(context["features_df"], parsed)

    return {
        "execution_summary": execution_summary,
        "flagged_items": flagged_items,
        "aggregate_result": aggregate_result,
    }