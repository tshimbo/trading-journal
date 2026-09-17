"""Command line: `tj add`, `tj positions`, `tj backtest`."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .backtest import sma_crossover
from .journal import append_trade, load_trades
from .models import Side, Trade
from .pnl import build_positions

DEFAULT_JOURNAL = Path("data/trades.csv")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tj", description="Paper-trading journal")
    p.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
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

    sub.add_parser("positions", help="show open positions and realized P&L")

    bt = sub.add_parser("backtest", help="SMA crossover on a CSV with a 'close' column")
    bt.add_argument("prices", type=Path)
    bt.add_argument("--short", type=int, default=5)
    bt.add_argument("--long", type=int, default=20)

    args = p.parse_args(argv)

    if args.cmd == "add":
        trade_date = args.date or datetime.now().astimezone().date()
        trade = Trade(
            trade_date, args.symbol, Side(args.side.upper()), args.quantity, args.price, args.fee
        )
        append_trade(args.journal, trade)
        print(f"logged {trade.side.value} {trade.quantity} {trade.symbol} @ {trade.price}")
    elif args.cmd == "positions":
        positions = build_positions(load_trades(args.journal))
        print(f"{'SYMBOL':<8}{'QTY':>10}{'COST BASIS':>14}{'REALIZED':>12}")
        for pos in positions.values():
            print(
                f"{pos.symbol:<8}{pos.quantity:>10}{pos.cost_basis:>14.2f}{pos.realized_pnl:>12.2f}"
            )
    elif args.cmd == "backtest":
        with args.prices.open(newline="") as f:
            closes = [Decimal(r["close"]) for r in csv.DictReader(f)]
        r = sma_crossover(closes, args.short, args.long)
        print(f"strategy: {r.final_equity}  buy&hold: {r.buy_and_hold_equity}  trades: {r.trades}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
