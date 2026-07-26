
import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

API_URL = "http://127.0.0.1:8000/query"
HEALTH_URL = "http://127.0.0.1:8000/health"

st.set_page_config(page_title="AML Suspicious Activity Agent", layout="wide")
st.title("🔍 AML Suspicious Activity Detection Agent")
try:
    health = requests.get(HEALTH_URL, timeout=3).json()
    if health.get("transactions_loaded") and health.get("customers_loaded"):
        st.success(f"Connected — {health['rows_loaded']} transactions loaded")
    else:
        st.error("Backend is up but dataset isn't loaded. Check data/ folder.")
except requests.exceptions.ConnectionError:
    st.error("Can't reach the API. Start it with: uvicorn interface.api:app --reload")
    st.stop()

examples = [
    "Find structuring patterns in the last 30 days",
    "Which customers made 10+ transactions under $10,000?",
    "Is customer C00205 suspicious?",
    "Which customer is the most suspicious?",
]
st.caption("Try an example, or type your own query below:")
cols = st.columns(len(examples))
for col, ex in zip(cols, examples):
    if col.button(ex, use_container_width=True):
        st.session_state["query"] = ex

query = st.text_input("Query", value=st.session_state.get("query", ""),
                       placeholder="e.g. Is customer C00205 suspicious?")

def safe_text(text: str) -> str:
    """Prevent Streamlit's Markdown renderer from treating $...$ as LaTeX math mode."""
    return text.replace("$", "\\$")

if st.button("Run", type="primary") and query:
    with st.spinner("Agent is thinking..."):
        try:
            resp = requests.post(API_URL, json={"query": query}, timeout=180)
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {e}")
            st.stop()
    if "error" in result:
        st.warning(result["error"])
    else:
        summary = result["execution_summary"]
        st.subheader("Execution Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Intent", summary["query_intent"])
        c2.metric("Pattern", summary["detected_pattern"] or "—")
        c3.metric("Tools Invoked", len(summary["tools_invoked"]))
        c4.metric("Filters", len(summary["filters_applied"]) or "none")
        st.caption(f"Tools: {' → '.join(summary['tools_invoked']) or 'none'}")

        
        if result.get("aggregate_result"):
            agg = result["aggregate_result"]
            st.subheader(f"Matching Customers ({agg['count']})")
            st.dataframe(pd.DataFrame(agg["matching_customers"], columns=["customer_id"]),
                         use_container_width=True, height=300)

        if result.get("flagged_items"):
            st.subheader(f"Flagged Items ({len(result['flagged_items'])})")
            for item in result["flagged_items"]:
                risk_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item["risk_level"], "⚪")
                with st.expander(f"{risk_color} {item['id']} — risk score {item['risk_score']:.2f} ({item['risk_level']})"):
                    st.write(safe_text(item["explanation"]))
                    st.caption(f"Recommended action: **{item['recommended_action']}**")

        if result.get("note"):
            st.info(safe_text(result["note"]))
        if result.get("ranked_customers"):
            label = result.get("ranked_label", "Ranked Customers")
            st.subheader(f"{label} ({len(result['ranked_customers'])})")
            for c in result["ranked_customers"]:
                risk_color = "🔴" if c["max_risk_score"] >= 0.5 else "🟡" if c["max_risk_score"] >= 0.25 else "🟢"
                with st.expander(
                    f"{risk_color} {c['customer_id']} — max risk {c['max_risk_score']:.2f} "
                    f"({c['flagged_transaction_count']} flagged transactions)"
                ):
                    st.write(safe_text(c["explanation"]))
                    st.caption(f"Recommended action: **{c['recommended_action']}**")