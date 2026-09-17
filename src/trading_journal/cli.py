"""Command line interface.

tj add buy NVDA 4 118.50 --fee 0.50
tj positions [--mark NVDA=131.20] [--live]
tj stats
tj quote SPY
tj fetch SPY --days 365 --out prices/SPY.csv
tj backtest prices/SPY.csv --short 5 --long 20 --fee-bps 5
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import __version__
from .backtest import sma_crossover
from .journal import append_trade, load_trades
from .models import Side, Trade
from .pnl import build_ledger, unrealized_pnl
from .prices import (
    PriceSource,
    PriceSourceError,
    YahooPriceSource,
    latest_close,
    read_bars_csv,
    write_bars_csv,
)
from .stats import trade_stats

DEFAULT_JOURNAL = Path("data/trades.csv")


def _today() -> date:
    return datetime.now().astimezone().date()


def _money(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _pct(value: Decimal | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def _parse_marks(items: Sequence[str]) -> dict[str, Decimal]:
    marks: dict[str, Decimal] = {}
    for item in items:
        symbol, sep, price = item.partition("=")
        try:
            if not sep:
                raise InvalidOperation
            marks[symbol.strip().upper()] = Decimal(price)
        except InvalidOperation as e:
            raise ValueError(f"--mark expects SYMBOL=PRICE, got {item!r}") from e
    return marks


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tj", description="Paper-trading journal")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL, help="trades CSV path")
    p.add_argument("--allow-short", action="store_true", help="let sells open short positions")
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="log a trade")
    add.add_argument("side", choices=["buy", "sell"])
    add.add_argument("symbol")
    add.add_argument("quantity", type=Decimal)
    add.add_argument("price", type=Decimal)
    add.add_argument("--fee", type=Decimal, default=Decimal(0))
    add.add_argument(
        "--date", type=date.fromisoformat, default=None, help="YYYY-MM-DD (default: today)"
    )

    pos = sub.add_parser("positions", help="open positions with realized and unrealized P&L")
    pos.add_argument("--mark", action="append", default=[], metavar="SYMBOL=PRICE")
    pos.add_argument("--live", action="store_true", help="use latest closes from Yahoo Finance")

    sub.add_parser("stats", help="win rate, profit factor, and P&L from closed trades")

    quote = sub.add_parser("quote", help="latest daily close")
    quote.add_argument("symbol")

    fetch = sub.add_parser("fetch", help="download daily closes to CSV")
    fetch.add_argument("symbol")
    fetch.add_argument("--days", type=int, default=365)
    fetch.add_argument("--out", type=Path)

    bt = sub.add_parser("backtest", help="SMA crossover on a CSV with a 'close' column")
    bt.add_argument("prices", type=Path)
    bt.add_argument("--short", type=int, default=5)
    bt.add_argument("--long", type=int, default=20)
    bt.add_argument("--fee-bps", type=Decimal, default=Decimal(0))
    bt.add_argument("--cash", type=Decimal, default=Decimal(10_000))
    return p


def main(
    argv: Sequence[str] | None = None,
    source: PriceSource | None = None,
    today: date | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    source = source or YahooPriceSource()
    today = today or _today()
    try:
        return _run(args, source, today)
    except (ValueError, PriceSourceError) as e:  # includes OversellError
        print(f"error: {e}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace, source: PriceSource, today: date) -> int:
    if args.cmd == "add":
        trade = Trade(
            args.date or today,
            args.symbol,
            Side(args.side.upper()),
            args.quantity,
            args.price,
            args.fee,
        )
        trades = load_trades(args.journal)
        build_ledger([*trades, trade], allow_short=args.allow_short)  # validate before saving
        append_trade(args.journal, trade)
        print(f"logged {trade.side.value} {trade.quantity} {trade.symbol} @ {trade.price}")
        return 0

    if args.cmd in {"positions", "stats"}:
        ledger = build_ledger(load_trades(args.journal), allow_short=args.allow_short)

    if args.cmd == "positions":
        marks = _parse_marks(args.mark)
        header = (
            f"{'SYMBOL':<8}{'QTY':>10}{'AVG':>12}{'MARK':>12}{'UNREALIZED':>13}{'REALIZED':>12}"
        )
        print(header)
        for p in sorted(ledger.positions.values(), key=lambda x: x.symbol):
            mark = None
            if p.quantity != 0:
                mark = marks.get(p.symbol)
                if mark is None and args.live:
                    mark = latest_close(source, p.symbol, today).close
            unreal = unrealized_pnl(p, mark) if mark is not None else None
            print(
                f"{p.symbol:<8}{p.quantity:>10}{_money(p.average_price):>12}{_money(mark):>12}"
                f"{_money(unreal):>13}{_money(p.realized_pnl):>12}"
            )
        print(f"\nTotal realized: {_money(ledger.realized_pnl)}")
        return 0

    if args.cmd == "stats":
        s = trade_stats(ledger.closed_trades)
        pf = "-" if s.profit_factor is None else f"{s.profit_factor:.2f}"
        print(f"Closed trades:  {s.trades} (wins: {s.wins}, losses: {s.losses})")
        print(f"Win rate:       {_pct(s.win_rate)}")
        print(f"Average win:    {_money(s.average_win)}")
        print(f"Average loss:   {_money(s.average_loss)}")
        print(f"Profit factor:  {pf}")
        print(f"Total P&L:      {_money(s.total_pnl)}")
        return 0

    if args.cmd == "quote":
        bar = latest_close(source, args.symbol, today)
        print(f"{args.symbol.upper()} {bar.close} (close {bar.day.isoformat()})")
        return 0

    if args.cmd == "fetch":
        bars = source.history(args.symbol, today - timedelta(days=args.days), today)
        if not bars:
            raise PriceSourceError(f"no prices returned for {args.symbol}")
        out = args.out or Path("prices") / f"{args.symbol.upper()}.csv"
        write_bars_csv(out, bars)
        print(f"wrote {len(bars)} daily closes to {out}")
        return 0

    # backtest
    closes = [bar.close for bar in read_bars_csv(args.prices)]
    r = sma_crossover(closes, args.short, args.long, args.cash, args.fee_bps)
    sharpe = "-" if r.sharpe is None else f"{r.sharpe:.2f}"
    print(f"Strategy equity:    {_money(r.final_equity)}")
    print(f"Buy and hold:       {_money(r.buy_and_hold_equity)}")
    print(f"Trades:             {r.trades}")
    print(f"Max drawdown:       {_pct(r.max_drawdown)}")
    print(f"Sharpe (annual):    {sharpe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
