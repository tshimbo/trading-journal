"""FIFO profit and loss.

FIFO = first in, first out: when you sell, the oldest shares you bought are the
ones considered sold. That's the default cost-basis method most US brokers use.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

from .models import Side, Trade


@dataclass
class Lot:
    quantity: Decimal
    unit_cost: Decimal  # price plus that buy's fee spread per share


@dataclass
class Position:
    symbol: str
    lots: deque[Lot] = field(default_factory=deque)
    realized_pnl: Decimal = Decimal(0)

    @property
    def quantity(self) -> Decimal:
        return sum((lot.quantity for lot in self.lots), Decimal(0))

    @property
    def cost_basis(self) -> Decimal:
        return sum((lot.quantity * lot.unit_cost for lot in self.lots), Decimal(0))


class OversellError(ValueError):
    """Raised when a sell exceeds the shares held (short selling isn't supported)."""


def build_positions(trades: list[Trade]) -> dict[str, Position]:
    """Replay trades in date order and return open positions plus realized P&L."""
    positions: dict[str, Position] = {}
    for t in sorted(trades, key=lambda x: x.trade_date):
        pos = positions.setdefault(t.symbol, Position(t.symbol))
        if t.side is Side.BUY:
            pos.lots.append(Lot(t.quantity, t.price + t.fee / t.quantity))
            continue
        if t.quantity > pos.quantity:
            raise OversellError(
                f"{t.trade_date}: selling {t.quantity} {t.symbol} but only hold {pos.quantity}"
            )
        remaining = t.quantity
        cost_removed = Decimal(0)
        while remaining > 0:
            lot = pos.lots[0]
            take = min(lot.quantity, remaining)
            cost_removed += take * lot.unit_cost
            lot.quantity -= take
            remaining -= take
            if lot.quantity == 0:
                pos.lots.popleft()
        pos.realized_pnl += t.quantity * t.price - t.fee - cost_removed
    return positions


def unrealized_pnl(position: Position, market_price: Decimal) -> Decimal:
    return position.quantity * market_price - position.cost_basis
