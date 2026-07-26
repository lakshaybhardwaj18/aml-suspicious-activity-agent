"""
Minimal API interface for the AML detection agent.
POST /query with {"query": "..."} → returns the agent's full response.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import os
from agent.orchestrator import handle_query

app = FastAPI(title="AML Suspicious Activity Detection Agent")

TX_PATH = os.environ.get("TX_PATH", "data/transactions.csv")
CUST_PATH = os.environ.get("CUST_PATH", "data/customers.csv")

df, cust_df = None, None
if os.path.exists(TX_PATH):
    df = pd.read_csv(TX_PATH)
if os.path.exists(CUST_PATH):
    cust_df = pd.read_csv(CUST_PATH)

if df is None or cust_df is None:
    print(f"⚠️  Missing data — expected {TX_PATH} and {CUST_PATH}")


class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def query_agent(request: QueryRequest):
    if df is None or cust_df is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded")
    try:
        return handle_query(request.query, df, cust_df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "transactions_loaded": df is not None,
        "customers_loaded": cust_df is not None,
        "rows_loaded": len(df) if df is not None else 0,
    }