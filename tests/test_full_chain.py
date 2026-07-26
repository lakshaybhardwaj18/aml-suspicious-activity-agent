import pandas as pd
from agent.orchestrator import run_agent
from agent.explainer import build_response

tx_df = pd.read_csv("data/transactions.csv")
cust_df = pd.read_csv("data/customers.csv")

for q in [
    "Find structuring patterns in the last 30 days",
    "Which customers made 10+ transactions under $10,000?",
    "Is customer C00205 suspicious?",
    "Is customer C99999 suspicious?",
]:
    context = run_agent(q, tx_df, cust_df)
    result = build_response(context)
    print(q)
    print(result)
    print("---")