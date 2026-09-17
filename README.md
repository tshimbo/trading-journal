# trading-journal

[![CI](https://github.com/tshimbo/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/tshimbo/trading-journal/actions/workflows/ci.yml)

A command-line paper-trading journal: log trades, see FIFO profit and loss, and backtest a simple moving-average strategy against buy-and-hold. Built test-first as a learning project for markets and test engineering.

> Educational project. Not investment advice, and the backtester is intentionally naive.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

tj add buy NVDA 4 118.50 --fee 0.50
tj add sell NVDA 1 131.20
tj positions
tj backtest examples/sample_prices.csv --short 5 --long 20
```
Trades are stored in `data/trades.csv` (git-ignored, so your real journal never gets pushed).

## How it's built
| Module | What it does | Key idea |
|---|---|---|
| `models.py` | `Trade` dataclass with validation | Money is `Decimal`, never `float` (0.1 + 0.2 ≠ 0.3 in floats) |
| `pnl.py` | Replays trades into positions | **FIFO** cost basis: the oldest shares are sold first |
| `journal.py` | CSV load/save | Bad rows fail loudly with the file and line number |
| `backtest.py` | SMA crossover vs. buy-and-hold | Kept simple on purpose so it's easy to test |
| `cli.py` | `tj add / positions / backtest` | Thin layer over the tested modules |

## Testing approach
- **26 tests, 99% coverage**, CI fails below 90%
- **Parametrized** tests for every validation rule
- **Property-based test** (Hypothesis): generates hundreds of random buy sequences and checks that selling everything always realizes exactly *proceeds − cost*
- **Factory fixture** (`make_trade`) so each test only states what it cares about
- CI on Python 3.11 and 3.12: `ruff` lint → `mypy --strict` → `pytest`

```bash
ruff check . && mypy src && pytest
```

## Roadmap
- [ ] Pull real daily prices (OpenBB or yfinance) behind an interface, with recorded fixtures for tests
- [ ] Unrealized P&L in `tj positions` using latest prices
- [ ] Short selling support
- [ ] Performance stats: win rate, max drawdown, Sharpe ratio
