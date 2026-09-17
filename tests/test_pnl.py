from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trading_journal.models import Side, Trade
from trading_journal.pnl import OversellError, build_positions, unrealized_pnl

D = Decimal


def test_fifo_sells_oldest_shares_first(make_trade):
    trades = [
        make_trade(trade_date=date(2026, 1, 1), quantity=D("10"), price=D("100")),
        make_trade(trade_date=date(2026, 1, 2), quantity=D("10"), price=D("200")),
        make_trade(trade_date=date(2026, 1, 3), side=Side.SELL, quantity=D("10"), price=D("150")),
    ]
    pos = build_positions(trades)["AAPL"]
    assert pos.realized_pnl == D("500")  # sold the $100 lot at $150
    assert pos.quantity == D("10")
    assert pos.cost_basis == D("2000")  # the $200 lot remains


def test_sell_spanning_two_lots(make_trade):
    trades = [
        make_trade(trade_date=date(2026, 1, 1), quantity=D("5"), price=D("10")),
        make_trade(trade_date=date(2026, 1, 2), quantity=D("5"), price=D("20")),
        make_trade(trade_date=date(2026, 1, 3), side=Side.SELL, quantity=D("7"), price=D("30")),
    ]
    pos = build_positions(trades)["AAPL"]
    assert pos.realized_pnl == D("7") * 30 - (5 * 10 + 2 * 20)
    assert pos.quantity == D("3")


def test_fees_reduce_profit(make_trade):
    trades = [
        make_trade(quantity=D("10"), price=D("100"), fee=D("5")),
        make_trade(
            trade_date=date(2026, 1, 3),
            side=Side.SELL,
            quantity=D("10"),
            price=D("100"),
            fee=D("5"),
        ),
    ]
    assert build_positions(trades)["AAPL"].realized_pnl == D("-10")


def test_trades_are_replayed_in_date_order_not_input_order(make_trade):
    sell = make_trade(trade_date=date(2026, 2, 1), side=Side.SELL, quantity=D("10"), price=D("120"))
    buy = make_trade(trade_date=date(2026, 1, 1), quantity=D("10"), price=D("100"))
    assert build_positions([sell, buy])["AAPL"].realized_pnl == D("200")


def test_overselling_raises(make_trade):
    with pytest.raises(OversellError, match="only hold 10"):
        build_positions(
            [
                make_trade(),
                make_trade(trade_date=date(2026, 1, 5), side=Side.SELL, quantity=D("11")),
            ]
        )


def test_unrealized_pnl(make_trade):
    pos = build_positions([make_trade(quantity=D("10"), price=D("100"))])["AAPL"]
    assert unrealized_pnl(pos, D("110")) == D("100")


# Property-based test: instead of hand-picking examples, Hypothesis generates
# hundreds of random buy/sell sequences and checks a rule that must ALWAYS hold.
money = st.decimals(min_value=D("0.01"), max_value=D("1000"), places=2)
qty = st.integers(min_value=1, max_value=100).map(D)


@given(buys=st.lists(st.tuples(qty, money), min_size=1, max_size=10), sell_price=money)
def test_selling_everything_realizes_exactly_proceeds_minus_cost(buys, sell_price):
    trades = [Trade(date(2026, 1, i + 1), "XYZ", Side.BUY, q, p) for i, (q, p) in enumerate(buys)]
    total_qty = sum((q for q, _ in buys), D("0"))
    total_cost = sum((q * p for q, p in buys), D("0"))
    trades.append(Trade(date(2026, 12, 31), "XYZ", Side.SELL, total_qty, sell_price))
    pos = build_positions(trades)["XYZ"]
    assert pos.quantity == 0
    assert pos.realized_pnl == total_qty * sell_price - total_cost
