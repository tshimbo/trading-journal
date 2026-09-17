from datetime import date
from decimal import Decimal

import pytest

from trading_journal.models import Side, Trade


@pytest.fixture
def make_trade():
    """Factory fixture: build a valid Trade, overriding only what a test cares about."""

    def _make(**overrides):
        fields = {
            "trade_date": date(2026, 1, 2),
            "symbol": "AAPL",
            "side": Side.BUY,
            "quantity": Decimal(10),
            "price": Decimal(100),
            "fee": Decimal(0),
        }
        fields.update(overrides)
        return Trade(**fields)

    return _make
