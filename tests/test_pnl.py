from datetime import date
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trading_journal.models import Side, Trade
from trading_journal.pnl import (
    OversellError,
    Position,
    build_ledger,
    build_positions,
    unrealized_pnl,
)


def day(n: int) -> date:
    return date(2026, 1, n)


class TestLongPositions:
    def test_fifo_sells_oldest_shares_first(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), quantity=D(10), price=D(100)),
            make_trade(trade_date=day(2), quantity=D(10), price=D(200)),
            make_trade(trade_date=day(3), side=Side.SELL, quantity=D(10), price=D(150)),
        ]
        pos = build_positions(trades)["AAPL"]
        assert pos.realized_pnl == D(500)
        assert pos.quantity == D(10)
        assert pos.cost_basis == D(2000)
        assert pos.average_price == D(200)

    def test_sell_spanning_two_lots(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), quantity=D(5), price=D(10)),
            make_trade(trade_date=day(2), quantity=D(5), price=D(20)),
            make_trade(trade_date=day(3), side=Side.SELL, quantity=D(7), price=D(30)),
        ]
        ledger = build_ledger(trades)
        assert ledger.positions["AAPL"].realized_pnl == 7 * 30 - (5 * 10 + 2 * 20)
        assert [c.quantity for c in ledger.closed_trades] == [D(5), D(2)]
        assert [c.opened for c in ledger.closed_trades] == [day(1), day(2)]

    def test_fees_reduce_profit(self, make_trade):
        trades = [
            make_trade(quantity=D(10), price=D(100), fee=D(5)),
            make_trade(trade_date=day(3), side=Side.SELL, quantity=D(10), price=D(100), fee=D(5)),
        ]
        assert build_positions(trades)["AAPL"].realized_pnl == D(-10)

    def test_trades_are_replayed_in_date_order(self, make_trade):
        sell = make_trade(trade_date=date(2026, 2, 1), side=Side.SELL, quantity=D(10), price=D(120))
        buy = make_trade(trade_date=day(1), quantity=D(10), price=D(100))
        assert build_positions([sell, buy])["AAPL"].realized_pnl == D(200)

    def test_closing_fully_goes_flat(self, make_trade):
        trades = [make_trade(), make_trade(trade_date=day(5), side=Side.SELL)]
        pos = build_positions(trades)["AAPL"]
        assert pos.quantity == 0
        assert pos.direction == 0
        assert pos.average_price is None


class TestShortPositions:
    def test_overselling_raises_without_allow_short(self, make_trade):
        with pytest.raises(OversellError, match="only hold 10"):
            build_positions(
                [make_trade(), make_trade(trade_date=day(5), side=Side.SELL, quantity=D(11))]
            )

    def test_short_profit_when_price_falls(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), side=Side.SELL, quantity=D(10), price=D(50)),
            make_trade(trade_date=day(2), side=Side.BUY, quantity=D(10), price=D(40)),
        ]
        ledger = build_ledger(trades, allow_short=True)
        assert ledger.positions["AAPL"].realized_pnl == D(100)
        assert ledger.closed_trades[0].direction == "SHORT"

    def test_short_loss_when_price_rises_with_fees(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), side=Side.SELL, quantity=D(10), price=D(50), fee=D(1)),
            make_trade(trade_date=day(2), side=Side.BUY, quantity=D(10), price=D(60), fee=D(1)),
        ]
        assert build_positions(trades, allow_short=True)["AAPL"].realized_pnl == D(-102)

    def test_sell_flips_long_to_short(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), quantity=D(10), price=D(100)),
            make_trade(trade_date=day(2), side=Side.SELL, quantity=D(15), price=D(110)),
        ]
        ledger = build_ledger(trades, allow_short=True)
        pos = ledger.positions["AAPL"]
        assert pos.realized_pnl == D(100)
        assert pos.quantity == D(-5)
        assert pos.direction == -1
        assert unrealized_pnl(pos, D(100)) == D(50)

    def test_buy_flips_short_to_long(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), side=Side.SELL, quantity=D(5), price=D(20)),
            make_trade(trade_date=day(2), side=Side.BUY, quantity=D(8), price=D(18)),
        ]
        pos = build_positions(trades, allow_short=True)["AAPL"]
        assert pos.realized_pnl == D(10)
        assert pos.quantity == D(3)
        assert pos.cost_basis == D(54)

    def test_fee_is_split_between_closing_and_opening_parts(self, make_trade):
        trades = [
            make_trade(trade_date=day(1), quantity=D(10), price=D(100)),
            make_trade(trade_date=day(2), side=Side.SELL, quantity=D(20), price=D(100), fee=D(20)),
        ]
        pos = build_positions(trades, allow_short=True)["AAPL"]
        assert pos.realized_pnl == D(-10)  # half the fee on the closing half
        assert pos.cost_basis == D(990)  # short proceeds net of the other half


class TestUnrealized:
    def test_long(self, make_trade):
        pos = build_positions([make_trade(quantity=D(10), price=D(100))])["AAPL"]
        assert unrealized_pnl(pos, D(110)) == D(100)

    def test_flat_is_zero(self):
        assert unrealized_pnl(Position("X"), D(123)) == 0


# Property-based tests: Hypothesis generates hundreds of random trade sequences
# and checks rules that must ALWAYS hold, instead of a few hand-picked examples.
money = st.decimals(min_value=D("0.01"), max_value=D(1000), places=2)
qty = st.integers(min_value=1, max_value=100).map(D)


@given(buys=st.lists(st.tuples(qty, money), min_size=1, max_size=10), sell_price=money)
def test_selling_everything_realizes_proceeds_minus_cost(buys, sell_price):
    trades = [Trade(date(2026, 1, i + 1), "XYZ", Side.BUY, q, p) for i, (q, p) in enumerate(buys)]
    total_qty = sum((q for q, _ in buys), D(0))
    total_cost = sum((q * p for q, p in buys), D(0))
    trades.append(Trade(date(2026, 12, 31), "XYZ", Side.SELL, total_qty, sell_price))
    ledger = build_ledger(trades)
    assert ledger.positions["XYZ"].quantity == 0
    assert ledger.realized_pnl == total_qty * sell_price - total_cost
    assert sum((c.pnl for c in ledger.closed_trades), D(0)) == ledger.realized_pnl


@given(
    steps=st.lists(
        st.tuples(st.sampled_from([Side.BUY, Side.SELL]), qty, money), min_size=1, max_size=25
    ),
    final_price=money,
)
def test_realized_plus_unrealized_equals_cash_flow(steps, final_price):
    """With no fees, total P&L must equal net cash flow plus the value of what's still held."""
    trades = [Trade(date(2026, 1, 1), "XYZ", side, q, p) for side, q, p in steps]
    pos = build_positions(trades, allow_short=True)["XYZ"]
    cash = sum(((-q * p) if s is Side.BUY else (q * p) for s, q, p in steps), D(0))
    assert pos.realized_pnl + unrealized_pnl(pos, final_price) == cash + pos.quantity * final_price
