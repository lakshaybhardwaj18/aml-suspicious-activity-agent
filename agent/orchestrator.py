"""
Agent Orchestrator — parses a user query, decides which tools to call,
and executes them in the right order.
Tool contract each function in tools/ must follow (agree on this with Member 2):
    run_eda(df, filters: dict) -> dict
    engineer_features(df, filters: dict, pattern: str) -> pd.DataFrame
    detect_anomalies(df, pattern: str) -> pd.DataFrame   # must include a 'risk_score' column
    classify_risk(df) -> pd.DataFrame                     # adds a 'risk_level' column
"""
from dataclasses import dataclass, field
from typing import Optional
import json
import pandas as pd
# --- Step 1: swap this for your actual LLM call (OpenAI/Anthropic/etc.) ---
import os
from dotenv import load_dotenv
load_dotenv()
from groq import Groq
_client = Groq(api_key=os.environ["GROQ_API_KEY"])

import time
from groq import RateLimitError

def call_llm(prompt: str, temperature: float = 0, model: str = "llama-3.3-70b-versatile", max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            response = _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait = 8 * (attempt + 1)  # 8s, 16s, 24s — enough to clear a TPM window
            time.sleep(wait)
@dataclass
class ParsedQuery:
    intent: str
    target_pattern: Optional[str] = None
    filters: dict = field(default_factory=dict)
    entity_id: Optional[str] = None
    min_transaction_count: Optional[int] = None   
    amount_threshold: Optional[float] = None      
    requested_count: Optional[int] = None  
    sort_direction: Optional[str] = None 

INTENT_PROMPT = """You are parsing a query for an AML detection agent.
Extract the following as JSON only, no extra text:
- intent: one of ["detect_pattern", "lookup_customer", "aggregate", "rank_customers", "general"]
- target_pattern: one of ["structuring", "smurfing", "layering", null]
- filters: object with any of date_range, country, transaction_type, segment
- entity_id: a specific customer/transaction ID mentioned, or null
- min_transaction_count: a minimum transaction count if mentioned, or null
- amount_threshold: a dollar amount threshold if mentioned, or null
- requested_count: for rank_customers queries, how many customers were asked for (default 5)
- sort_direction: "desc" for most/highest-risk/most suspicious customers,
  "asc" for least/lowest-risk/safest/cleanest/not-suspicious customers.
  Use "rank_customers" intent for BOTH directions — "find customers who are NOT
  suspicious" is rank_customers with sort_direction="asc", not a different intent.

Query: "{query}"
"""
def parse_query(query: str) -> ParsedQuery:
    """Turn the raw user query into a structured ParsedQuery."""
    prompt = INTENT_PROMPT.format(query=query)
    raw = call_llm(prompt)
    data = json.loads(raw)
    return ParsedQuery(**data)

def build_plan(parsed: ParsedQuery) -> list[str]:
    """
    Decide which tools to invoke, in order, based on parsed intent.
    This is the "dynamic execution plan" the spec requires — not every
    query runs every tool.
    """
    if parsed.intent == "lookup_customer":
        # Single-entity lookup: skip EDA, go straight to detection for that entity
        return ["engineer_features", "detect_anomalies", "classify_risk"]
    if parsed.intent == "aggregate":
        # Simple counting/threshold query — no ML needed
        return ["engineer_features"]
    if parsed.intent == "rank_customers":
        # "Most suspicious customer" style queries: need full scoring,
        # aggregated to customer level downstream in explainer.py
        return ["engineer_features", "detect_anomalies", "classify_risk"]
    if parsed.intent == "detect_pattern":
        # Full flow, but skip EDA if a specific pattern is already named
        if parsed.target_pattern:
            return ["engineer_features", "detect_anomalies", "classify_risk"]
        return ["run_eda", "engineer_features", "detect_anomalies", "classify_risk"]
    if parsed.intent == "general":
        # Chitchat / meta questions ("who are you?", "what can you do?") need
        # no tools at all -- explainer.py returns a canned response for these.
        return []
    # Fallback for anything the LLM mis-labels outside the known intents:
    # run everything so we at least surface something useful.
    return ["run_eda", "engineer_features", "detect_anomalies", "classify_risk"]
def _classify_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Bucket final_score into low/medium/high — same thresholds as reporting.py's
    risk_bucket(), just reusable per-query instead of a batch script."""
    df = df.copy()
    def bucket(score):
        if score >= 0.5:
            return "high"
        elif score >= 0.25:
            return "medium"
        return "low"
    df["risk_level"] = df["final_score"].apply(bucket)
    df["risk_score"] = df["final_score"]  # keep explainer.py's expected column name
    return df


def execute_plan(plan: list[str], df: pd.DataFrame, customers_df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    from tools import eda_tool, feature_engineering, anomaly_detection

    working_df = df
    if parsed.entity_id:
        working_df = df[df["customer_id"] == parsed.entity_id]
        if working_df.empty:
            return {"error": f"No customer found with ID {parsed.entity_id}"}

    # Translate your filter keys to theirs
    tool_filters = {
        "start_date": parsed.filters.get("date_from"),
        "end_date": parsed.filters.get("date_to"),
        "country": parsed.filters.get("country"),
        "transaction_type": parsed.filters.get("transaction_type"),
    }

    context = {"raw_df": working_df, "filters": parsed.filters}

    if "run_eda" in plan:
        context["eda_summary"] = eda_tool.run_eda(working_df, customers_df, tool_filters)

    if "engineer_features" in plan:
        scoped = eda_tool.apply_filters(working_df, tool_filters)
        context["features_df"] = feature_engineering.engineer_features(scoped, customers_df)

    if "detect_anomalies" in plan:
        context["scored_df"] = anomaly_detection.detect_anomalies(context["features_df"], use_ml=True)

    if "classify_risk" in plan:
        context["risk_df"] = _classify_risk(context["scored_df"])

    return context
def run_agent(query: str, df: pd.DataFrame, customers_df: pd.DataFrame = None) -> dict:
    parsed = parse_query(query)
    plan = build_plan(parsed)
    context = execute_plan(plan, df, customers_df, parsed)
    context["parsed_query"] = parsed
    context["plan_used"] = plan
    return context
def handle_query(query: str, df: pd.DataFrame, customers_df: pd.DataFrame = None) -> dict:
    from agent.explainer import build_response
    context = run_agent(query, df, customers_df)
    return build_response(context)