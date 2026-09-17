from decimal import Decimal

import pytest

from trading_journal.backtest import sma, sma_crossover

D = Decimal


def test_sma_values():
    assert sma([D(1), D(2), D(3), D(4)], 2) == [None, D("1.5"), D("2.5"), D("3.5")]


def test_sma_rejects_bad_window():
    with pytest.raises(ValueError):
        sma([D(1)], 0)


def test_flat_prices_never_trade():
    r = sma_crossover([D(100)] * 30, short=3, long=10)
    assert r.trades == 0
    assert r.final_equity == r.buy_and_hold_equity == D("10000.00")


def test_uptrend_then_crash_exits_before_bottom():
    up = [D(100 + i) for i in range(30)]
    down = [D(129 - 5 * i) for i in range(1, 20)]
    r = sma_crossover(up + down, short=3, long=10)
    assert r.trades >= 2
    assert r.beat_buy_and_hold


@pytest.mark.parametrize("short,long", [(10, 10), (20, 5)])
def test_invalid_windows(short, long):
    with pytest.raises(ValueError):
        sma_crossover([D(1)] * 30, short, long)


def test_needs_prices():
    with pytest.raises(ValueError):
        sma_crossover([D(1)])
