from datetime import date
from decimal import Decimal as D

import pytest

from trading_journal.pnl import ClosedTrade
from trading_journal.stats import max_drawdown, period_returns, sharpe_ratio, trade_stats


def closed(pnl: str) -> ClosedTrade:
    return ClosedTrade("X", "LONG", D(1), date(2026, 1, 1), date(2026, 1, 2), D(pnl))


def test_trade_stats_mixed():
    s = trade_stats([closed("100"), closed("-50"), closed("200"), closed("0")])
    assert (s.trades, s.wins, s.losses) == (4, 2, 1)
    assert s.win_rate == D("0.5")
    assert s.average_win == D(150)
    assert s.average_loss == D(-50)
    assert s.profit_factor == D(6)
    assert s.total_pnl == D(250)


def test_trade_stats_empty():
    s = trade_stats([])
    assert s.trades == 0
    assert s.win_rate is s.profit_factor is s.average_win is s.average_loss is None


def test_profit_factor_none_without_losses():
    assert trade_stats([closed("5")]).profit_factor is None


def test_max_drawdown():
    assert max_drawdown([D(100), D(120), D(90), D(130), D(117)]) == D("0.25")
    assert max_drawdown([D(1), D(2), D(3)]) == 0
    assert max_drawdown([]) == 0


def test_period_returns_skips_zero_base():
    assert period_returns([D(100), D(110), D(0), D(5)]) == [D("0.1"), D(-1)]


def test_sharpe():
    assert sharpe_ratio([D("0.01")]) is None
    assert sharpe_ratio([D("0.01"), D("0.01")]) is None  # zero volatility
    # mean 0.00625, sample std 0.011087 -> 0.00625 / 0.011087 = 0.5637 (per period)
    value = sharpe_ratio([D("0.01"), D("-0.005"), D("0.02"), D("0.0")], periods_per_year=1)
    assert value == pytest.approx(0.5637, rel=1e-3)
    annual = sharpe_ratio([D("0.01"), D("-0.005"), D("0.02"), D("0.0")])
    assert annual == pytest.approx(0.5637 * 252**0.5, rel=1e-3)
