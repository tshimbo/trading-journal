from datetime import date
from decimal import Decimal as D

import pytest

from trading_journal.cli import main
from trading_journal.prices import Bar

TODAY = date(2026, 3, 2)


class FakeSource:
    """In-memory price source so CLI tests never touch the network."""

    def __init__(self, closes: dict[str, list[Bar]]):
        self.closes = closes

    def history(self, symbol, start, end):
        return [b for b in self.closes.get(symbol.upper(), []) if start <= b.day <= end]


SOURCE = FakeSource(
    {"NVDA": [Bar(date(2026, 2, 27), D(140))], "SPY": [Bar(date(2026, 2, 26), D(600))]}
)


def run(capsys, *argv, journal=None):
    args = ["--journal", str(journal)] if journal else []
    code = main([*args, *argv], source=SOURCE, today=TODAY)
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture
def journal(tmp_path, capsys):
    j = tmp_path / "t.csv"
    assert run(capsys, "add", "buy", "nvda", "4", "100", "--date", "2026-01-02", journal=j)[0] == 0
    assert run(capsys, "add", "sell", "NVDA", "1", "130", "--date", "2026-01-05", journal=j)[0] == 0
    return j


def test_add_defaults_to_today(tmp_path, capsys):
    j = tmp_path / "t.csv"
    run(capsys, "add", "buy", "spy", "1", "500", journal=j)
    assert "2026-03-02,SPY,BUY" in j.read_text()


def test_positions_with_manual_mark(journal, capsys):
    code, out, _ = run(capsys, "positions", "--mark", "NVDA=110", journal=journal)
    assert code == 0
    assert "NVDA" in out and "30.00" in out and "110.00" in out
    assert "Total realized: 30.00" in out


def test_positions_live_uses_price_source(journal, capsys):
    _, out, _ = run(capsys, "positions", "--live", journal=journal)
    assert "140.00" in out and "120.00" in out  # 3 shares * (140 - 100)


def test_closed_position_ignores_mark(tmp_path, capsys):
    j = tmp_path / "t.csv"
    run(capsys, "add", "buy", "SPY", "1", "500", "--date", "2026-01-02", journal=j)
    run(capsys, "add", "sell", "SPY", "1", "510", "--date", "2026-01-03", journal=j)
    _, out, _ = run(capsys, "positions", "--mark", "SPY=999", "--live", journal=j)
    assert "999" not in out and "600" not in out
    assert "10.00" in out


def test_positions_without_mark_shows_dash(journal, capsys):
    _, out, _ = run(capsys, "positions", journal=journal)
    assert " - " in out


def test_bad_mark_is_a_clean_error(journal, capsys):
    code, _, err = run(capsys, "positions", "--mark", "NVDA:110", journal=journal)
    assert code == 1 and "SYMBOL=PRICE" in err


def test_oversell_rejected_and_not_saved(journal, capsys):
    before = journal.read_text()
    code, _, err = run(capsys, "add", "sell", "NVDA", "10", "130", journal=journal)
    assert code == 1 and "--allow-short" in err
    assert journal.read_text() == before


def test_allow_short(journal, capsys):
    code, _, _ = run(capsys, "--allow-short", "add", "sell", "NVDA", "10", "130", journal=journal)
    assert code == 0
    _, out, _ = run(capsys, "--allow-short", "positions", journal=journal)
    assert "-7" in out


def test_stats(journal, capsys):
    _, out, _ = run(capsys, "stats", journal=journal)
    assert "Closed trades:  1 (wins: 1, losses: 0)" in out
    assert "Win rate:       100.0%" in out
    assert "Profit factor:  -" in out


def test_stats_with_a_loss(journal, capsys):
    run(capsys, "add", "sell", "NVDA", "1", "90", "--date", "2026-01-06", journal=journal)
    _, out, _ = run(capsys, "stats", journal=journal)
    assert "Profit factor:  3.00" in out


def test_quote(capsys):
    code, out, _ = run(capsys, "quote", "spy")
    assert code == 0 and "SPY 600 (close 2026-02-26)" in out


def test_quote_unknown_symbol(capsys):
    code, _, err = run(capsys, "quote", "NOPE")
    assert code == 1 and "no recent prices" in err


def test_fetch_writes_csv(tmp_path, capsys):
    out_file = tmp_path / "prices" / "SPY.csv"
    code, out, _ = run(capsys, "fetch", "SPY", "--days", "30", "--out", str(out_file))
    assert code == 0 and "wrote 1" in out
    assert out_file.read_text().splitlines() == ["date,close", "2026-02-26,600"]


def test_fetch_default_path(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run(capsys, "fetch", "SPY")
    assert (tmp_path / "prices" / "SPY.csv").exists()


def test_fetch_nothing_returned(capsys):
    code, _, err = run(capsys, "fetch", "NOPE")
    assert code == 1 and "no prices returned" in err


def test_backtest_command(tmp_path, capsys):
    prices = tmp_path / "p.csv"
    prices.write_text("close\n" + "\n".join(str(100 + (i % 9) * 2) for i in range(60)))
    code, out, _ = run(
        capsys, "backtest", str(prices), "--short", "3", "--long", "10", "--fee-bps", "5"
    )
    assert code == 0
    for label in ("Strategy equity", "Buy and hold", "Max drawdown", "Sharpe"):
        assert label in out


def test_backtest_bad_file(tmp_path, capsys):
    code, _, err = run(capsys, "backtest", str(tmp_path / "missing.csv"))
    assert code == 1 and "not found" in err


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "1.0.0" in capsys.readouterr().out
