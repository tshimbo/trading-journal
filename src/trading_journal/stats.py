"""Performance statistics for closed trades and equity curves.

All inputs are Decimal. Ratios that involve square roots (Sharpe) are returned
as float because they are estimates, not money.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from .pnl import ClosedTrade

ZERO = Decimal(0)
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class TradeStats:
    trades: int
    wins: int
    losses: int
    total_pnl: Decimal
    win_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    profit_factor: Decimal | None  # gross profit / gross loss; None when there are no losses


def trade_stats(closed: list[ClosedTrade]) -> TradeStats:
    wins = [c.pnl for c in closed if c.pnl > 0]
    losses = [c.pnl for c in closed if c.pnl < 0]
    gross_win = sum(wins, ZERO)
    gross_loss = -sum(losses, ZERO)
    n = len(closed)
    return TradeStats(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        total_pnl=sum((c.pnl for c in closed), ZERO),
        win_rate=Decimal(len(wins)) / n if n else None,
        average_win=gross_win / len(wins) if wins else None,
        average_loss=-gross_loss / len(losses) if losses else None,
        profit_factor=gross_win / gross_loss if gross_loss else None,
    )


def period_returns(equity: list[Decimal]) -> list[Decimal]:
    """Simple return between consecutive equity values."""
    return [(b - a) / a for a, b in pairwise(equity) if a != 0]


def max_drawdown(equity: list[Decimal]) -> Decimal:
    """Largest peak-to-trough decline as a positive fraction (0.25 means -25%)."""
    peak = None
    worst = ZERO
    for value in equity:
        if peak is None or value > peak:
            peak = value
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def sharpe_ratio(
    returns: list[Decimal], periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float | None:
    """Annualized Sharpe ratio with a 0% risk-free rate. None if it can't be computed."""
    if len(returns) < 2:
        return None
    values = [float(r) for r in returns]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return mean / std * math.sqrt(periods_per_year)
