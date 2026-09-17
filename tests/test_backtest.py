from decimal import Decimal as D

import pytest

from trading_journal.backtest import sma, sma_crossover


def test_sma_values():
    assert sma([D(1), D(2), D(3), D(4)], 2) == [None, D("1.5"), D("2.5"), D("3.5")]


def test_sma_rejects_bad_window():
    with pytest.raises(ValueError):
        sma([D(1)], 0)


def test_flat_prices_never_trade():
    r = sma_crossover([D(100)] * 30, short=3, long=10)
    assert r.trades == 0
    assert r.final_equity == r.buy_and_hold_equity == D("10000.00")
    assert r.max_drawdown == 0
    assert r.sharpe is None
    assert len(r.equity_curve) == 30


def test_uptrend_then_crash_exits_before_bottom():
    up = [D(100 + i) for i in range(30)]
    down = [D(129 - 5 * i) for i in range(1, 20)]
    r = sma_crossover(up + down, short=3, long=10)
    assert r.trades >= 2
    assert r.beat_buy_and_hold
    assert 0 < r.max_drawdown < D("0.2")
    assert r.sharpe is not None


def test_fees_lower_returns():
    prices = [D(100 + (i % 7) * 3) for i in range(60)]
    free = sma_crossover(prices, 2, 5)
    costly = sma_crossover(prices, 2, 5, fee_bps=D(25))
    assert costly.trades == free.trades > 0
    assert costly.final_equity < free.final_equity


@pytest.mark.parametrize("short,long", [(10, 10), (20, 5), (0, 5)])
def test_invalid_windows(short, long):
    with pytest.raises(ValueError):
        sma_crossover([D(1)] * 30, short, long)


def test_needs_prices():
    with pytest.raises(ValueError):
        sma_crossover([D(1)])


def test_negative_fee_rejected():
    with pytest.raises(ValueError):
        sma_crossover([D(1)] * 30, 2, 5, fee_bps=D(-1))
