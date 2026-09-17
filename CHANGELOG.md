# Changelog

## 1.0.0 - 2026-09-17

### Added
- Short selling: sells beyond your holdings open a short position when `--allow-short` is set
- Closed-trade tracking and `tj stats`: win rate, average win and loss, profit factor
- `tj positions --mark SYMBOL=PRICE` and `--live` for unrealized P&L
- Price data behind a `PriceSource` interface: CSV folders and Yahoo Finance daily closes
- `tj quote` and `tj fetch` commands
- Backtest trading costs (`--fee-bps`), equity curve, max drawdown, and Sharpe ratio
- Property-based test that realized plus unrealized P&L always equals net cash flow
- Recorded Yahoo response fixture so tests never hit the network
- CI on Python 3.11 to 3.13, format check, CLI smoke test, wheel build, secret scanning, no-emoji check
- MIT license

### Changed
- Invalid trades are rejected before they are written to the journal
- CLI errors print a clear message and exit with code 1 instead of a traceback

## 0.1.0 - 2026-09-16
- Initial release: trade model, FIFO P&L for long positions, CSV journal, SMA crossover backtest
