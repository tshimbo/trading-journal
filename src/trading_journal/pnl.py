"""FIFO profit and loss for long and short positions.

FIFO = first in, first out: when a position is reduced, the oldest open lot is
closed first. This matches the default cost-basis method most US brokers use.

A position is long when quantity > 0 and short when quantity < 0. Selling more
than you hold flips the position short, but only if ``allow_short`` is True;
otherwise it raises ``OversellError``, which catches typos in the journal.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .models import Side, Trade

ZERO = Decimal(0)


class OversellError(ValueError):
    """Raised when a sell exceeds the shares held and short selling is not allowed."""


@dataclass
class Lot:
    """An open slice of a position.

    ``quantity`` is always positive. ``unit_basis`` is the cost per share for a
    long lot (price plus fee per share) or the proceeds per share for a short
    lot (price minus fee per share).
    """

    quantity: Decimal
    unit_basis: Decimal
    opened: date


@dataclass(frozen=True)
class ClosedTrade:
    """A completed round trip (or part of one), used for performance stats."""

    symbol: str
    direction: str  # "LONG" or "SHORT"
    quantity: Decimal
    opened: date
    closed: date
    pnl: Decimal


@dataclass
class Position:
    symbol: str
    direction: int = 0  # 1 long, -1 short, 0 flat
    lots: deque[Lot] = field(default_factory=deque)
    realized_pnl: Decimal = ZERO

    @property
    def quantity(self) -> Decimal:
        """Signed share count: positive when long, negative when short."""
        return self.direction * sum((lot.quantity for lot in self.lots), ZERO)

    @property
    def cost_basis(self) -> Decimal:
        """Total basis of open lots (cost for longs, proceeds for shorts)."""
        return sum((lot.quantity * lot.unit_basis for lot in self.lots), ZERO)

    @property
    def average_price(self) -> Decimal | None:
        qty = abs(self.quantity)
        return self.cost_basis / qty if qty else None


@dataclass
class Ledger:
    positions: dict[str, Position]
    closed_trades: list[ClosedTrade]

    @property
    def realized_pnl(self) -> Decimal:
        return sum((p.realized_pnl for p in self.positions.values()), ZERO)


def build_ledger(trades: list[Trade], allow_short: bool = False) -> Ledger:
    """Replay trades in date order into positions and closed round trips.

    Trades on the same date keep their journal order (the sort is stable).
    """
    positions: dict[str, Position] = {}
    closed: list[ClosedTrade] = []
    for t in sorted(trades, key=lambda x: x.trade_date):
        pos = positions.setdefault(t.symbol, Position(t.symbol))
        _apply(pos, t, allow_short, closed)
    return Ledger(positions, closed)


def build_positions(trades: list[Trade], allow_short: bool = False) -> dict[str, Position]:
    return build_ledger(trades, allow_short).positions


def _apply(pos: Position, t: Trade, allow_short: bool, closed: list[ClosedTrade]) -> None:
    trade_dir = 1 if t.side is Side.BUY else -1
    fee_per_share = t.fee / t.quantity
    remaining = t.quantity

    # 1) Reduce an opposite-direction position first.
    if pos.direction == -trade_dir:
        while remaining > 0 and pos.lots:
            lot = pos.lots[0]
            take = min(lot.quantity, remaining)
            if pos.direction == 1:  # closing a long with a sell
                pnl = take * (t.price - fee_per_share - lot.unit_basis)
                label = "LONG"
            else:  # covering a short with a buy
                pnl = take * (lot.unit_basis - t.price - fee_per_share)
                label = "SHORT"
            pos.realized_pnl += pnl
            closed.append(ClosedTrade(pos.symbol, label, take, lot.opened, t.trade_date, pnl))
            lot.quantity -= take
            remaining -= take
            if lot.quantity == 0:
                pos.lots.popleft()
        if not pos.lots:
            pos.direction = 0

    # 2) Whatever is left opens (or adds to) a position in the trade's direction.
    if remaining > 0:
        if trade_dir == -1 and not allow_short:
            held = t.quantity - remaining
            raise OversellError(
                f"{t.trade_date}: selling {t.quantity} {t.symbol} but only hold {held}. "
                "Pass allow_short=True (CLI: --allow-short) to open a short."
            )
        basis = t.price + fee_per_share if trade_dir == 1 else t.price - fee_per_share
        pos.lots.append(Lot(remaining, basis, t.trade_date))
        pos.direction = trade_dir


def unrealized_pnl(position: Position, market_price: Decimal) -> Decimal:
    """Profit or loss if the open position were closed at ``market_price`` (before fees)."""
    qty = abs(position.quantity)
    if position.direction == 1:
        return qty * market_price - position.cost_basis
    if position.direction == -1:
        return position.cost_basis - qty * market_price
    return ZERO
