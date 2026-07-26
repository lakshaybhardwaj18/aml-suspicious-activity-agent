"""
Feature Engineering Tool
-------------------------
Builds AML-relevant features ON DEMAND for whatever transaction slice the
Agent Orchestrator hands over (already filtered by date range / segment /
country / transaction type). Deliberately recomputes everything from raw
`amount` + `timestamp` rather than trusting the dataset's pre-baked global
columns, because those are computed over the FULL history and would be
wrong/stale for a filtered query (e.g. "just March" or "just UAE").

Public entry point: engineer_features(tx_df, customers_df=None) -> pd.DataFrame
"""

import pandas as pd
import numpy as np


def _rolling_customer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-customer rolling/frequency features, using a real time-based
    rolling window (not row-count based), so gaps in the query slice
    don't distort the numbers."""
    df = df.sort_values(["customer_id", "timestamp"]).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if df.empty:
        # orchestrator filter matched nothing -- return the empty frame with
        # the expected extra columns so downstream tools don't KeyError
        for col in ["tx_count_24h", "tx_count_7d", "tx_count_30d", "rolling_sum_24h",
                    "rolling_sum_7d", "velocity_24h", "amount_deviation",
                    "unique_counterparties_7d"]:
            df[col] = pd.Series(dtype="float64")
        return df

    out_frames = []
    for cust_id, g in df.groupby("customer_id", sort=False):
        g = g.set_index("timestamp").sort_index()

        # transaction frequency: count of txns in trailing windows
        g["tx_count_24h"] = g["amount"].rolling("24h").count()
        g["tx_count_7d"] = g["amount"].rolling("7D").count()
        g["tx_count_30d"] = g["amount"].rolling("30D").count()

        # rolling sums (structuring/smurfing signal: many small amounts summing large)
        g["rolling_sum_24h"] = g["amount"].rolling("24h").sum()
        g["rolling_sum_7d"] = g["amount"].rolling("7D").sum()

        # velocity: amount moved per hour over trailing 24h window
        g["velocity_24h"] = g["rolling_sum_24h"] / 24.0

        # amount deviation from this customer's own historical mean (z-score-like,
        # using expanding window so it only looks at PAST transactions -> no leakage)
        expanding_mean = g["amount"].expanding().mean().shift(1)
        expanding_std = g["amount"].expanding().std().shift(1)
        g["amount_deviation"] = (g["amount"] - expanding_mean) / expanding_std.replace(0, np.nan)
        g["amount_deviation"] = g["amount_deviation"].fillna(0)

        # unique counterparties trailing 7d (layering signal)
        # rolling() can't operate on strings directly, so factorize to numeric
        # codes first, then count distinct codes in the window.
        if "counterparty_id" in g.columns:
            codes = pd.Series(pd.factorize(g["counterparty_id"])[0], index=g.index)
            g["unique_counterparties_7d"] = (
                codes.rolling("7D").apply(lambda x: pd.Series(x).nunique(), raw=False)
            )

        out_frames.append(g.reset_index())

    return pd.concat(out_frames, ignore_index=True)


def _rapid_cashout_flag(df: pd.DataFrame, hours: int = 24) -> pd.Series:
    """Flags customers whose deposit is followed by a withdrawal/transfer of a
    similar magnitude within `hours` -- classic rapid cash-out / layering signal."""
    df = df.sort_values(["customer_id", "timestamp"])
    flags = pd.Series(False, index=df.index)

    for cust_id, g in df.groupby("customer_id"):
        deposits = g[g["transaction_type"] == "Deposit"]
        moves = g[g["transaction_type"].isin(["Withdrawal", "Transfer"])]
        for idx, dep in deposits.iterrows():
            window = moves[
                (moves["timestamp"] > dep["timestamp"]) &
                (moves["timestamp"] <= dep["timestamp"] + pd.Timedelta(hours=hours)) &
                (moves["amount"] >= 0.8 * dep["amount"])
            ]
            if len(window) > 0:
                flags.loc[dep.name] = True
                flags.loc[window.index] = True
    return flags


def engineer_features(tx_df: pd.DataFrame, customers_df: pd.DataFrame = None,
                       compute_rapid_cashout: bool = True) -> pd.DataFrame:
    """Main Feature Engineering Tool entry point."""
    df = tx_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = _rolling_customer_features(df)

    if compute_rapid_cashout:
        df["rapid_cashout_flag"] = _rapid_cashout_flag(df)
    else:
        df["rapid_cashout_flag"] = False

    if customers_df is not None:
        df = df.merge(customers_df, on="customer_id", how="left", suffixes=("", "_cust"))
        # amount as a fraction of income -> flags disproportionate transaction sizes
        df["amount_to_income_ratio"] = df["amount"] / df["income"].replace(0, np.nan)

    return df


if __name__ == "__main__":
    tx = pd.read_csv("/home/claude/aml_project/data/transactions.csv")
    cust = pd.read_csv("/home/claude/aml_project/data/customers.csv")

    # Sanity-test on a manageable slice first (single country) before full run
    sample = tx[tx["country"] == "UAE"].copy()
    print("Testing on UAE slice:", sample.shape)
    feat = engineer_features(sample, cust, compute_rapid_cashout=True)
    print(feat[["customer_id", "timestamp", "amount", "tx_count_24h", "tx_count_7d",
                "rolling_sum_24h", "velocity_24h", "amount_deviation",
                "unique_counterparties_7d", "rapid_cashout_flag"]].head(10))
    feat.to_csv("/home/claude/aml_project/outputs/tables/features_uae_sample.csv", index=False)
    print("\nSaved sample. Shape:", feat.shape)
