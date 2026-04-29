# FX Live Trading Setup

## Prerequisites

1. OANDA account (demo recommended for testing)
2. API token from OANDA portal
3. Account ID

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```
   OANDA_API_TOKEN=your-actual-token
   OANDA_ACCOUNT_ID=your-actual-account-id
   OANDA_ENVIRONMENT=practice
   ```

3. Run backtest mode (default):
   ```bash
   python -m src.main
   ```

4. Run live trading mode (ONE CYCLE):
   ```bash
   python -m src.main --live
   ```

## Safety Features

- Default environment is `practice` (demo)
- Circuit breaker stops trading after daily loss limit
- Trading hours restriction (configurable)
- All trades and errors are logged to `logs/`

## ⚠️ IMPORTANT

- ALWAYS test with `practice` environment first
- NEVER set `OANDA_ENVIRONMENT=live` until you are 100% confident
- Monitor logs closely: `tail -f logs/trades.log logs/errors.log`
