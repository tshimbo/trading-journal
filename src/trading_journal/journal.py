"""Read and write trades as CSV, so your journal is a plain file you own."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Side, Trade

FIELDS = ["trade_date", "symbol", "side", "quantity", "price", "fee"]


def load_trades(path: Path) -> list[Trade]:
    if not path.exists():
        return []
    trades: list[Trade] = []
    with path.open(newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                trades.append(
                    Trade(
                        trade_date=date.fromisoformat(row["trade_date"]),
                        symbol=row["symbol"],
                        side=Side(row["side"].upper()),
                        quantity=Decimal(row["quantity"]),
                        price=Decimal(row["price"]),
                        fee=Decimal(row.get("fee") or "0"),
                    )
                )
            except (KeyError, ValueError, InvalidOperation) as e:
                raise ValueError(f"{path}:{line_no}: bad row {row!r} ({e})") from e
    return trades


def append_trade(path: Path, trade: Trade) -> None:
    new_file = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "trade_date": trade.trade_date.isoformat(),
                "symbol": trade.symbol,
                "side": trade.side.value,
                "quantity": str(trade.quantity),
                "price": str(trade.price),
                "fee": str(trade.fee),
            }
        )
