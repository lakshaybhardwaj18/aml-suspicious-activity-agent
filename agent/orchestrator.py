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

def call_llm(prompt: str) -> str:
    """Send a prompt to Groq and return raw text response."""
    response = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},  # forces valid JSON output
    )
    return response.choices[0].message.content
    raise NotImplementedError("Plug in your LLM client here")
@dataclass
class ParsedQuery:
    intent: str
    target_pattern: Optional[str] = None
    filters: dict = field(default_factory=dict)
    entity_id: Optional[str] = None
    min_transaction_count: Optional[int] = None   # NEW
    amount_threshold: Optional[float] = None        # NEW

INTENT_PROMPT = """You are parsing a query for an AML detection agent.
Extract the following as JSON only, no extra text:
- intent: one of ["detect_pattern", "lookup_customer", "aggregate", "general"]
- target_pattern: one of ["structuring", "smurfing", "layering", null]
- filters: object with any of date_range, country, transaction_type, segment
- entity_id: a specific customer/transaction ID mentioned, or null
- min_transaction_count: a minimum transaction count if mentioned, or null
- amount_threshold: a dollar amount threshold if mentioned, or null

IMPORTANT: Only set intent="detect_pattern" and a target_pattern if the user
explicitly names or clearly asks to find a laundering pattern (e.g. "find
structuring", "detect smurfing"). If the query is just a count/threshold
question — even if it resembles a known pattern — classify it as "aggregate"
and leave target_pattern null. The agent should not assume analytical intent
the user didn't ask for.

Example:
Query: "Which customers made 10+ transactions under $10,000?"
Output: {{"intent": "aggregate", "target_pattern": null, "filters": {{}}, "entity_id": null, "min_transaction_count": 10, "amount_threshold": 10000}}

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
    if parsed.intent == "detect_pattern":
        # Full flow, but skip EDA if a specific pattern is already named
        if parsed.target_pattern:
            return ["engineer_features", "detect_anomalies", "classify_risk"]
        return ["run_eda", "engineer_features", "detect_anomalies", "classify_risk"]
    # Fallback: run everything
    return ["run_eda", "engineer_features", "detect_anomalies", "classify_risk"]

def execute_plan(plan: list[str], df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    from tools import eda, feature_engineering, anomaly_detection, risk_classification

    working_df = df
    if parsed.entity_id:
        working_df = df[df["customer_id"] == parsed.entity_id]
        if working_df.empty:
            return {"error": f"No customer found with ID {parsed.entity_id}"}

    context = {"raw_df": working_df, "filters": parsed.filters}
    if "run_eda" in plan:
        context["eda_summary"] = eda.run_eda(working_df, parsed.filters)
    if "engineer_features" in plan:
        context["features_df"] = feature_engineering.engineer_features(
            working_df, parsed.filters, parsed.target_pattern
        )
    if "detect_anomalies" in plan:
        context["scored_df"] = anomaly_detection.detect_anomalies(
            context["features_df"], parsed.target_pattern
        )
    if "classify_risk" in plan:
        context["risk_df"] = risk_classification.classify_risk(context["scored_df"])
    return context

def run_agent(query: str, df: pd.DataFrame) -> dict:
    """Entry point: takes a raw user query + dataset, returns full context for explainer.py"""
    parsed = parse_query(query)
    plan = build_plan(parsed)
    context = execute_plan(plan, df, parsed)
    context["parsed_query"] = parsed
    context["plan_used"] = plan
    return context
def handle_query(query: str, df: pd.DataFrame) -> dict:
    """Single entry point: raw query + dataset in, final response out."""
    from agent.explainer import build_response
    context = run_agent(query, df)
    return build_response(context)