from trading_journal.cli import main


def test_add_then_positions(tmp_path, capsys):
    j = tmp_path / "t.csv"
    assert (
        main(["--journal", str(j), "add", "buy", "nvda", "4", "100", "--date", "2026-01-02"]) == 0
    )
    assert (
        main(["--journal", str(j), "add", "sell", "NVDA", "1", "130", "--date", "2026-01-05"]) == 0
    )
    main(["--journal", str(j), "positions"])
    out = capsys.readouterr().out
    assert "NVDA" in out and "30.00" in out


def test_backtest_command(tmp_path, capsys):
    prices = tmp_path / "p.csv"
    prices.write_text("close\n" + "\n".join(str(100 + i) for i in range(40)))
    main(["backtest", str(prices), "--short", "3", "--long", "10"])
    assert "buy&hold" in capsys.readouterr().out
