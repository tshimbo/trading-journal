"""A deliberately simple moving-average crossover backtest.

Rule: go all-in when the short average crosses above the long average,
exit to cash when it crosses back below. Compared against buy-and-hold.
This exists to practice testing, not to pick stocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def sma(values: list[Decimal], window: int) -> list[Decimal | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[Decimal | None] = []
    running = Decimal(0)
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

    @property
    def beat_buy_and_hold(self) -> bool:
        return self.final_equity > self.buy_and_hold_equity


def sma_crossover(
    closes: list[Decimal], short: int = 5, long: int = 20, starting_cash: Decimal = Decimal(10000)
) -> BacktestResult:
    if short >= long:
        raise ValueError("short window must be smaller than long window")
    if len(closes) < 2:
        raise ValueError("need at least two prices")
    s, l_ = sma(closes, short), sma(closes, long)
    cash, shares, trades = starting_cash, Decimal(0), 0
    for i, price in enumerate(closes):
        if s[i] is None or l_[i] is None:
            continue
        if shares == 0 and s[i] > l_[i]:  # type: ignore[operator]
            shares, cash, trades = cash / price, Decimal(0), trades + 1
        elif shares > 0 and s[i] < l_[i]:  # type: ignore[operator]
            cash, shares, trades = shares * price, Decimal(0), trades + 1
    final = cash + shares * closes[-1]
    buy_hold = starting_cash / closes[0] * closes[-1]
    return BacktestResult(
        final.quantize(Decimal("0.01")), buy_hold.quantize(Decimal("0.01")), trades
    )
