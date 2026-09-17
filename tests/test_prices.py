import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from trading_journal.prices import (
    Bar,
    CsvPriceSource,
    PriceSourceError,
    YahooPriceSource,
    latest_close,
    parse_yahoo_chart,
    read_bars_csv,
    write_bars_csv,
)

FIXTURES = Path(__file__).parent / "fixtures"


def recorded(name: str):
    """Fake network: returns a saved response and records the URL requested."""
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return (FIXTURES / name).read_bytes()

    return fetch, calls


def test_yahoo_parses_recorded_response_and_skips_nulls():
    fetch, calls = recorded("yahoo_with_null_gap.json")
    bars = YahooPriceSource(fetch=fetch).history("spy", date(2026, 1, 5), date(2026, 1, 8))
    assert [b.close for b in bars] == [D("590.1200"), D("593.5000"), D("588.2500")]
    assert bars[0].day == date(2026, 1, 5)
    assert "/SPY?" in calls[0] and "interval=1d" in calls[0]


def test_yahoo_real_recorded_response():
    """Response captured from the live endpoint (SPY, Sep 5-15 2025), trimmed to the fields we use."""
    fetch, _ = recorded("yahoo_spy_2025-09.json")
    bars = YahooPriceSource(fetch=fetch).history("SPY", date(2025, 9, 5), date(2025, 9, 15))
    assert len(bars) == 7
    assert (bars[0].day, bars[0].close) == (date(2025, 9, 5), D("647.2400"))
    assert (bars[-1].day, bars[-1].close) == (date(2025, 9, 15), D("660.9100"))


def test_yahoo_error_payload():
    with pytest.raises(PriceSourceError, match="No data found"):
        parse_yahoo_chart(
            {"chart": {"result": None, "error": {"description": "No data found"}}}, "ZZZ"
        )


@pytest.mark.parametrize(
    "payload", [{}, {"chart": {"result": []}}, [], {"chart": {"result": [{}]}}]
)
def test_yahoo_unexpected_shapes(payload):
    with pytest.raises(PriceSourceError, match="unexpected response"):
        parse_yahoo_chart(payload, "SPY")


def test_yahoo_network_failure_is_wrapped():
    def boom(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(PriceSourceError, match="offline"):
        YahooPriceSource(fetch=boom).history("SPY", date(2026, 1, 1), date(2026, 1, 2))


def test_yahoo_bad_json_is_wrapped():
    with pytest.raises(PriceSourceError):
        YahooPriceSource(fetch=lambda url: b"<html>").history(
            "SPY", date(2026, 1, 1), date(2026, 1, 2)
        )


def test_csv_round_trip_and_source(tmp_path):
    bars = [Bar(date(2026, 1, 2), D("10.5")), Bar(date(2026, 1, 5), D(11))]
    write_bars_csv(tmp_path / "ABC.csv", bars)
    assert read_bars_csv(tmp_path / "ABC.csv") == bars
    src = CsvPriceSource(tmp_path)
    assert src.history("abc", date(2026, 1, 3), date(2026, 1, 9)) == bars[1:]
    assert latest_close(src, "ABC", date(2026, 1, 6)).close == D(11)


def test_csv_without_date_column(tmp_path):
    (tmp_path / "p.csv").write_text("Close\n1\n2\n")
    assert [b.close for b in read_bars_csv(tmp_path / "p.csv")] == [D(1), D(2)]


@pytest.mark.parametrize(
    "content,message",
    [("date,open\n2026-01-01,1\n", "needs a 'close'"), ("date,close\nnot-a-date,1\n", "bad value")],
)
def test_csv_errors(tmp_path, content, message):
    (tmp_path / "p.csv").write_text(content)
    with pytest.raises(PriceSourceError, match=message):
        read_bars_csv(tmp_path / "p.csv")


def test_csv_missing_file(tmp_path):
    with pytest.raises(PriceSourceError, match="not found"):
        read_bars_csv(tmp_path / "missing.csv")


def test_latest_close_no_data(tmp_path):
    write_bars_csv(tmp_path / "OLD.csv", [Bar(date(2020, 1, 1), D(1))])
    with pytest.raises(PriceSourceError, match="no recent prices"):
        latest_close(CsvPriceSource(tmp_path), "OLD", date(2026, 1, 1))


def test_fixture_is_valid_json():
    json.loads((FIXTURES / "yahoo_with_null_gap.json").read_text())
