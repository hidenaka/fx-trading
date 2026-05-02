"""個別取引ログから勝敗要因を集計."""
from __future__ import annotations

import pandas as pd


def analyze_trades(
    trades_df: pd.DataFrame,
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    spy_daily: pd.DataFrame | None = None,
) -> dict:
    """One (strategy, symbol) trade log -> diagnostic stats."""
    n_trades = len(trades_df)
    if n_trades == 0:
        empty_hour = pd.DataFrame(columns=["hour", "n_trades", "n_wins", "win_rate", "avg_pnl_pct"])
        empty_change = pd.DataFrame(columns=["bucket", "n_trades", "win_rate", "avg_pnl_pct"])
        empty_hold = pd.DataFrame(columns=["bucket", "n_trades", "win_rate", "avg_pnl_pct"])
        out = {
            "n_trades": 0,
            "n_wins": 0,
            "win_rate": float("nan"),
            "avg_pnl_pct": float("nan"),
            "total_pnl_pct": 0.0,
            "exit_breakdown": {"stop": 0, "target": 0, "time": 0},
            "avg_pnl_by_exit_type": {"stop": float("nan"), "target": float("nan"), "time": float("nan")},
            "wr_by_hour_of_day": empty_hour,
            "wr_by_day_open_change": empty_change,
            "wr_by_holding_bars": empty_hold,
        }
        if spy_daily is not None:
            out["wr_by_spy_regime"] = pd.DataFrame(columns=["regime", "n_trades", "win_rate", "avg_pnl_pct"])
        return out

    df = trades_df.copy()
    df["is_win"] = df["pnl_pct"] > 0
    df["pnl_pct_pct"] = df["pnl_pct"] * 100.0  # convert fraction -> %

    n_wins = int(df["is_win"].sum())
    win_rate = n_wins / n_trades
    avg_pnl_pct = float(df["pnl_pct_pct"].mean())
    total_pnl_pct = float(df["pnl_pct_pct"].sum())

    exit_counts = df["exit_type"].value_counts().to_dict()
    exit_breakdown = {k: int(exit_counts.get(k, 0)) for k in ["stop", "target", "time"]}

    avg_by_exit = {}
    for ex in ["stop", "target", "time"]:
        sub = df[df["exit_type"] == ex]
        avg_by_exit[ex] = float(sub["pnl_pct_pct"].mean()) if len(sub) else float("nan")

    # Hour of day in NY tz
    ny = df["entry_ts"].dt.tz_convert("America/New_York")
    df["hour_ny"] = ny.dt.hour
    hod = (
        df.groupby("hour_ny")
        .agg(
            n_trades=("is_win", "size"),
            n_wins=("is_win", "sum"),
            avg_pnl_pct=("pnl_pct_pct", "mean"),
        )
        .reset_index()
        .rename(columns={"hour_ny": "hour"})
    )
    hod["win_rate"] = hod["n_wins"] / hod["n_trades"]
    hod = hod[["hour", "n_trades", "n_wins", "win_rate", "avg_pnl_pct"]]

    # Day-open intraday change at entry: close[entry_ts] / first_open_of_NY_day - 1
    bars = bars_5min.copy()
    bars_ny_date = pd.Series(bars.index.tz_convert("America/New_York").date, index=bars.index)
    first_open_per_day = bars.groupby(bars_ny_date)["open"].transform("first")
    intraday_change = (bars["close"] - first_open_per_day) / first_open_per_day  # fraction

    df["intraday_change"] = intraday_change.reindex(df["entry_ts"]).values

    def _bucket(x: float) -> str:
        if x < -0.01:
            return "< -1%"
        if x < 0.0:
            return "-1%..0%"
        if x < 0.01:
            return "0%..+1%"
        return "> +1%"

    df["intraday_bucket"] = df["intraday_change"].apply(lambda x: _bucket(x) if pd.notna(x) else "n/a")
    bucket_order = ["< -1%", "-1%..0%", "0%..+1%", "> +1%"]
    change_grp = (
        df[df["intraday_bucket"].isin(bucket_order)]
        .groupby("intraday_bucket")
        .agg(
            n_trades=("is_win", "size"),
            n_wins=("is_win", "sum"),
            avg_pnl_pct=("pnl_pct_pct", "mean"),
        )
        .reset_index()
        .rename(columns={"intraday_bucket": "bucket"})
    )
    change_grp["win_rate"] = change_grp["n_wins"] / change_grp["n_trades"]
    change_grp["__o"] = change_grp["bucket"].apply(lambda b: bucket_order.index(b))
    change_grp = change_grp.sort_values("__o").drop(columns="__o").reset_index(drop=True)
    change_grp = change_grp[["bucket", "n_trades", "win_rate", "avg_pnl_pct"]]

    # Holding bars buckets
    def _hold_bucket(b: int) -> str:
        if b <= 3:
            return "1-3"
        if b <= 12:
            return "4-12"
        if b <= 39:
            return "13-39"
        return "40-78"

    df["hold_bucket"] = df["bars_held"].apply(_hold_bucket)
    hold_order = ["1-3", "4-12", "13-39", "40-78"]
    hold_grp = (
        df.groupby("hold_bucket")
        .agg(
            n_trades=("is_win", "size"),
            n_wins=("is_win", "sum"),
            avg_pnl_pct=("pnl_pct_pct", "mean"),
        )
        .reset_index()
        .rename(columns={"hold_bucket": "bucket"})
    )
    hold_grp["win_rate"] = hold_grp["n_wins"] / hold_grp["n_trades"]
    hold_grp["__o"] = hold_grp["bucket"].apply(lambda b: hold_order.index(b))
    hold_grp = hold_grp.sort_values("__o").drop(columns="__o").reset_index(drop=True)
    hold_grp = hold_grp[["bucket", "n_trades", "win_rate", "avg_pnl_pct"]]

    out = {
        "n_trades": n_trades,
        "n_wins": n_wins,
        "win_rate": win_rate,
        "avg_pnl_pct": avg_pnl_pct,
        "total_pnl_pct": total_pnl_pct,
        "exit_breakdown": exit_breakdown,
        "avg_pnl_by_exit_type": avg_by_exit,
        "wr_by_hour_of_day": hod,
        "wr_by_day_open_change": change_grp,
        "wr_by_holding_bars": hold_grp,
    }

    if spy_daily is not None:
        spy = spy_daily.copy()
        spy["prev_close"] = spy["close"].shift(1)
        spy["regime"] = (spy["close"] > spy["prev_close"]).map({True: "up", False: "down"})
        spy = spy.dropna(subset=["prev_close"])

        # Build a date -> regime mapping using NY-local dates
        if spy.index.tz is not None:
            spy_dates = pd.Series(spy.index.tz_convert("America/New_York").date, index=spy.index)
        else:
            spy_dates = pd.Series(pd.to_datetime(spy.index).date, index=spy.index)

        regime_by_date = pd.Series(spy["regime"].values, index=spy_dates.values)

        df["entry_ny_date"] = df["entry_ts"].dt.tz_convert("America/New_York").dt.date
        df["regime"] = df["entry_ny_date"].map(regime_by_date)

        regime_grp = (
            df.dropna(subset=["regime"])
            .groupby("regime")
            .agg(
                n_trades=("is_win", "size"),
                n_wins=("is_win", "sum"),
                avg_pnl_pct=("pnl_pct_pct", "mean"),
            )
            .reset_index()
        )
        regime_grp["win_rate"] = regime_grp["n_wins"] / regime_grp["n_trades"]
        regime_grp = regime_grp[["regime", "n_trades", "win_rate", "avg_pnl_pct"]]
        out["wr_by_spy_regime"] = regime_grp

    return out
