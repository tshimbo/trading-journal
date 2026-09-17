from decimal import Decimal

import pytest


def test_symbol_is_normalized(make_trade):
    assert make_trade(symbol="  msft ").symbol == "MSFT"


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("symbol", "   ", "symbol is required"),
        ("quantity", Decimal(0), "quantity must be positive"),
        ("quantity", Decimal(-1), "quantity must be positive"),
        ("price", Decimal(0), "price must be positive"),
        ("fee", Decimal("-0.01"), "fee cannot be negative"),
    ],
)
def test_invalid_trades_are_rejected(make_trade, field, value, message):
    with pytest.raises(ValueError, match=message):
        make_trade(**{field: value})


def test_trade_is_immutable(make_trade):
    t = make_trade()
    with pytest.raises(AttributeError):
        t.price = Decimal(1)  # type: ignore[misc]
