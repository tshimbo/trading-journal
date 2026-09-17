from datetime import date
from decimal import Decimal

import pytest

from trading_journal.journal import append_trade, load_trades
from trading_journal.models import Side


def test_round_trip(tmp_path, make_trade):
    path = tmp_path / "trades.csv"
    original = [
        make_trade(),
        make_trade(trade_date=date(2026, 1, 9), side=Side.SELL, fee=Decimal("1.5")),
    ]
    for t in original:
        append_trade(path, t)
    assert load_trades(path) == original


def test_missing_file_is_empty_journal(tmp_path):
    assert load_trades(tmp_path / "nope.csv") == []


def test_bad_row_reports_line_number(tmp_path):
    path = tmp_path / "trades.csv"
    path.write_text("trade_date,symbol,side,quantity,price,fee\n2026-01-02,AAPL,HOLD,1,1,0\n")
    with pytest.raises(ValueError, match=r"trades.csv:2"):
        load_trades(path)
