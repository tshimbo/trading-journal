# trading-journal

[![CI](https://github.com/tshimbo/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/tshimbo/trading-journal/actions/workflows/ci.yml)
[![Security](https://github.com/tshimbo/trading-journal/actions/workflows/security.yml/badge.svg)](https://github.com/tshimbo/trading-journal/actions/workflows/security.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A command-line paper-trading journal. Log trades, track FIFO profit and loss for long and short positions, review your win rate and profit factor, pull daily prices, and backtest a simple moving-average strategy against buy-and-hold.

Built test-first as a personal project for learning markets and test engineering.

> Educational project. Not investment advice. The backtester is intentionally simple.

## Install
```bash
git clone https://github.com/tshimbo/trading-journal.git
cd trading-journal
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage
```bash
# Log trades (defaults to today's date)
tj add buy NVDA 20 135.00 --fee 1
tj add sell NVDA 20 128.40 --fee 1 --date 2026-01-28

# Open positions with unrealized P&L
tj positions --mark SPY=600          # use a price you type in
tj positions --live                  # use the latest daily close

# How your closed trades performed
tj stats

# Prices
tj quote SPY
tj fetch SPY --days 365              # saves prices/SPY.csv

# Backtest a 5/20-day moving-average crossover with 5 bps trading costs
tj backtest prices/SPY.csv --short 5 --long 20 --fee-bps 5

# Short selling is off by default so a typo can't open a short by accident
tj --allow-short add sell TSLA 5 250
```

Try it on the sample data without logging anything:
```bash
tj --journal examples/sample_trades.csv stats
tj backtest examples/sample_prices.csv
```

Your real journal lives in `data/trades.csv`, which is git-ignored so it is never pushed.

## How it works
| Module | Responsibility | Key idea |
|---|---|---|
| `models.py` | `Trade` with validation | Money is `Decimal`, never `float`, so cents never drift |
| `pnl.py` | Replays trades into positions and closed trades | FIFO lots, long and short, fees split per share |
| `stats.py` | Win rate, profit factor, max drawdown, Sharpe | Pure functions, easy to test |
| `prices.py` | `PriceSource` interface, CSV and Yahoo sources | Network access is injected, so tests use recorded data |
| `backtest.py` | SMA crossover with trading costs | Returns the full equity curve |
| `journal.py` | CSV load and save | Bad rows fail with the file name and line number |
| `cli.py` | `tj` commands | Thin layer; every command is tested end to end |

## Testing approach
- 75 tests, 98% coverage; CI fails below 95%
- **Property-based tests** (Hypothesis) generate random trade sequences and check invariants, for example: realized plus unrealized P&L always equals net cash flow plus the value of open positions
- **Recorded fixtures**: a real Yahoo Finance response is saved in `tests/fixtures`, so tests are fast and never depend on the network
- **Fakes over mocks**: CLI tests pass an in-memory price source instead of patching
- **Parametrized** tests for every validation rule and error path
- CI on Python 3.11, 3.12, and 3.13: ruff lint and format, mypy strict, pytest, a CLI smoke test, and a clean wheel install
- Security workflow: gitleaks scans the full git history, blocks committed `.env` files, and enforces a no-emoji style rule

```bash
ruff check . && ruff format --check . && mypy src && pytest
```

## Limitations
- The Yahoo Finance chart endpoint is unofficial and can change or rate-limit without notice
- Prices are daily closes only; no dividends, splits, or intraday data
- The backtest trades at the close on the signal day and ignores slippage beyond `--fee-bps`

## License
MIT
