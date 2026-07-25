# tests/sample_queries.py
from agent.orchestrator import call_llm, parse_query, build_plan

# Step 1: sanity check
print(call_llm('Return this as JSON: {"status": "ok"}'))

# Step 2 & 3: real test queries
test_queries = [
    "Find structuring patterns in the last 30 days",
    "Which customers made 10+ transactions under $10,000?",
    "Is customer ID 4521 suspicious?",
]

for q in test_queries:
    parsed = parse_query(q)
    plan = build_plan(parsed)
    print(q, "→", parsed, "→ plan:", plan)