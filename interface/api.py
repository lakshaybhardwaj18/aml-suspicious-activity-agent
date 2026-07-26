"""
Minimal API interface for the AML detection agent.
POST /query with {"query": "..."} → returns the agent's full response.
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
from agent.orchestrator import handle_query

app = FastAPI(title="AML Suspicious Activity Detection Agent")

# Load your dataset once at startup — swap this path for wherever
# your Kaggle download / synthetic CSV actually lives.
DATASET_PATH = os.environ.get("DATASET_PATH", "data/transactions.csv")
df = pd.read_csv(DATASET_PATH)


class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def query_agent(request: QueryRequest):
    try:
        result = handle_query(request.query, df)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "rows_loaded": len(df)}