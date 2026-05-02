# Equity Bot — Operations Runbook (Plan 2.0 Paper MVP)

## What this bot does

Runs three scheduled jobs against Alpaca **Paper** account:
- **Morning** (~9:31 ET): scans SPY/QQQ/IWM/XLK for gap-fill setups, places bracket orders if signal fires.
- **Intraday** (every 5 min, 9:35-15:50 ET): scans XLK for mean-reversion setups, places bracket order if signal fires.
- **EOD** (~15:55 ET): closes any still-open positions at market, writes daily P&L summary.

**Sizing (β-mode):** 25% of account equity per trade, capped at $2,500. Max 3 concurrent positions.

**Halt rule:** if today's realized loss exceeds 2% of equity, new entries are suppressed.

## First-time setup

1. `cd /Users/hideakimacbookair/自動トレード`
2. Confirm `equity_trading/.env` contains valid Paper API keys (look for `ALPACA_BASE_URL=https://paper-api.alpaca.markets`).
3. Run a connectivity check:
   ```
   python3 equity_trading/scripts/run_bot.py --check
   ```
   Expected output: account number, equity, cash. No orders.
4. If equity is much larger than $10k, the β $2,500 cap still applies, but consider depositing-out via Alpaca dashboard to mirror β assumptions.

## Daily routine (manual, Monday-Friday only)

Run these three commands at the indicated NY-time wall-clock points. Use `nohup` or a terminal multiplexer if you want them detached.

| Time (NY) | Command |
|-----------|---------|
| 09:31 | `python3 equity_trading/scripts/run_bot.py --morning` |
| 09:35-15:50, every 5 min | `python3 equity_trading/scripts/run_bot.py --intraday` |
| 15:55 | `python3 equity_trading/scripts/run_bot.py --eod` |

For the intraday loop you can use a simple shell loop:
```
for i in $(seq 1 75); do
  python3 equity_trading/scripts/run_bot.py --intraday
  sleep 300
done
```

(75 × 5 min = 6.25 hours, covers the full session.)

## Reading the daily summary

After `--eod` runs, the script prints a Markdown summary. SQLite also has the data:

- `equity_trading/data/trades.sqlite` is the source of truth.
- Tables: `positions` (every trade), `bot_runs` (audit log), `daily_pnl` (one row per day).

Quick check:
```
sqlite3 equity_trading/data/trades.sqlite \
  "SELECT trade_date, realized_pnl_usd, n_entries, n_exits FROM daily_pnl ORDER BY trade_date DESC LIMIT 7"
```

## What can go wrong

1. **Insufficient bars error in logs.** Means the Alpaca API returned fewer bars than expected. Most often happens during pre-market or right at the open. Wait a minute and re-run.
2. **Circuit halt triggered.** Bot logs `circuit halted: ...` in `bot_runs.error_message`. No new entries until next day.
3. **Order rejected (PDT rule).** A bracket order was rejected. Check Alpaca dashboard — Paper can hit pattern-day-trader rules under $25k equity. Currently we don't auto-detect; if you see "PDT" errors, reduce trade frequency.
4. **`--morning` placed orders on a holiday.** The bot doesn't (yet) check the market calendar. Don't run on US holidays.

## Where to look when something is wrong

```
sqlite3 equity_trading/data/trades.sqlite \
  "SELECT id, run_type, started_at_utc, status, error_message FROM bot_runs ORDER BY id DESC LIMIT 10"
```

## When to stop

Plan 2.0 is a Paper validation phase. Run for 4-12 weeks, accumulate ~50+ trades across all strategies, then compare actual stats vs Phase 0 expectations:

| Strategy | Expected WR | Expected avg P&L |
|----------|-------------|-------------------|
| gap_fill SPY 0.3% | ~0.72 | ~0.14% |
| gap_fill QQQ 0.5% | ~0.75 | ~0.29% |
| gap_fill IWM 1.0% | ~0.69 | ~0.43% |
| gap_fill XLK 0.5% | ~0.77 | ~1.40% |
| mean_reversion XLK 0.40 | ~0.64 | ~0.03% |

If actual WR/EV is within ±10 pts of expected → strategies generalize, proceed to Plan 2.1 (live deployment).
If actual is below expected → diagnose with `equity_trading/scripts/run_phase0_diagnostic.py` against the new live trades.
