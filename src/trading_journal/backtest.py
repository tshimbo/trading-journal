"""A deliberately simple moving-average crossover backtest.

Rule: go all-in when the short average crosses above the long average, and exit
to cash when it crosses back below. Results are compared against buy-and-hold.
Trading costs are modeled as basis points per trade (5 bps = 0.05%).

This exists to practice testing and learn how strategies are evaluated, not to
pick stocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .stats import max_drawdown, period_returns, sharpe_ratio

ZERO = Decimal(0)
BPS = Decimal(10_000)


def sma(values: list[Decimal], window: int) -> list[Decimal | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[Decimal | None] = []
    running = ZERO
    for i, v in enumerate(values):
        running += v
        if i >= window:
            running -= values[i - window]
        out.append(running / window if i >= window - 1 else None)
    return out


@dataclass(frozen=True)
class BacktestResult:
    final_equity: Decimal
    buy_and_hold_equity: Decimal
    trades: int
    equity_curve: tuple[Decimal, ...]

    @property
    def beat_buy_and_hold(self) -> bool:
        return self.final_equity > self.buy_and_hold_equity

    @property
    def max_drawdown(self) -> Decimal:
        return max_drawdown(list(self.equity_curve))

    @property
    def sharpe(self) -> float | None:
        return sharpe_ratio(period_returns(list(self.equity_curve)))


def sma_crossover(
    closes: list[Decimal],
    short: int = 5,
    long: int = 20,
    starting_cash: Decimal = Decimal(10_000),
    fee_bps: Decimal = ZERO,
) -> BacktestResult:
    if short <= 0 or short >= long:
        raise ValueError("windows must satisfy 0 < short < long")
    if len(closes) < 2:
        raise ValueError("need at least two prices")
    if fee_bps < 0:
        raise ValueError("fee_bps cannot be negative")
    cost = fee_bps / BPS
    s, lng = sma(closes, short), sma(closes, long)
    cash, shares, trades = starting_cash, ZERO, 0
    curve: list[Decimal] = []
    for i, price in enumerate(closes):
        fast, slow = s[i], lng[i]
        if fast is not None and slow is not None:
            if shares == 0 and fast > slow:
                shares, cash, trades = cash * (1 - cost) / price, ZERO, trades + 1
            elif shares > 0 and fast < slow:
                cash, shares, trades = shares * price * (1 - cost), ZERO, trades + 1
        curve.append(cash + shares * price)
    buy_hold = starting_cash * (1 - cost) / closes[0] * closes[-1]
    cents = Decimal("0.01")
    return BacktestResult(
        final_equity=curve[-1].quantize(cents),
        buy_and_hold_equity=buy_hold.quantize(cents),
        trades=trades,
        equity_curve=tuple(curve),
    )
