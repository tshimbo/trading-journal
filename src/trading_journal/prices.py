"""Price data behind a small interface so the rest of the code never talks to the network.

``PriceSource`` is a Protocol: anything with a ``history(symbol, start, end)``
method works. Tests use an in-memory source; real use can read a CSV export or
Yahoo Finance's public chart endpoint.
"""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    day: date
    close: Decimal


class PriceSourceError(RuntimeError):
    """Raised when prices can't be loaded or parsed."""


class PriceSource(Protocol):
    def history(self, symbol: str, start: date, end: date) -> list[Bar]: ...


def latest_close(source: PriceSource, symbol: str, today: date) -> Bar:
    """Most recent close on or before ``today``, looking back up to 10 days for weekends/holidays."""
    bars = source.history(symbol, today - timedelta(days=10), today)
    if not bars:
        raise PriceSourceError(f"no recent prices for {symbol}")
    return bars[-1]


def write_bars_csv(path: Path, bars: list[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "close"])
        for bar in bars:
            writer.writerow([bar.day.isoformat(), str(bar.close)])


def read_bars_csv(path: Path) -> list[Bar]:
    """Read a CSV with ``date`` and ``close`` columns (extra columns are ignored)."""
    try:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            fields = {name.lower().strip(): name for name in (reader.fieldnames or [])}
            if "close" not in fields:
                raise PriceSourceError(f"{path}: needs a 'close' column")
            date_col = fields.get("date")
            bars = []
            for i, row in enumerate(reader):
                day = (
                    date.fromisoformat(row[date_col]) if date_col else date.min + timedelta(days=i)
                )
                bars.append(Bar(day, Decimal(row[fields["close"]])))
    except FileNotFoundError as e:
        raise PriceSourceError(f"{path}: file not found") from e
    except (ValueError, InvalidOperation) as e:
        raise PriceSourceError(f"{path}: bad value ({e})") from e
    return sorted(bars, key=lambda b: b.day)


@dataclass
class CsvPriceSource:
    """One CSV per symbol in a folder, e.g. ``prices/SPY.csv``."""

    folder: Path

    def history(self, symbol: str, start: date, end: date) -> list[Bar]:
        path = self.folder / f"{symbol.upper()}.csv"
        return [b for b in read_bars_csv(path) if start <= b.day <= end]


Fetcher = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "trading-journal/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        body: bytes = response.read()
        return body


@dataclass
class YahooPriceSource:
    """Daily closes from Yahoo Finance's public chart endpoint.

    This is an unofficial endpoint: fine for a personal journal, not for anything
    that matters. ``fetch`` is injectable so tests use recorded responses and
    never hit the network.
    """

    fetch: Fetcher = _http_get
    base_url: str = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def history(self, symbol: str, start: date, end: date) -> list[Bar]:
        query = urllib.parse.urlencode(
            {
                "period1": _epoch(start),
                "period2": _epoch(end + timedelta(days=1)),
                "interval": "1d",
                "events": "history",
            }
        )
        url = f"{self.base_url}{urllib.parse.quote(symbol.upper())}?{query}"
        try:
            payload = json.loads(self.fetch(url))
        except (OSError, ValueError) as e:
            raise PriceSourceError(f"could not load prices for {symbol}: {e}") from e
        return parse_yahoo_chart(payload, symbol)


def _epoch(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def parse_yahoo_chart(payload: object, symbol: str) -> list[Bar]:
    try:
        chart = payload["chart"]  # type: ignore[index]
        if chart.get("error"):
            raise PriceSourceError(f"{symbol}: {chart['error'].get('description', chart['error'])}")
        result = chart["result"][0]
        stamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as e:
        raise PriceSourceError(f"{symbol}: unexpected response shape") from e
    bars = []
    for ts, close in zip(stamps, closes, strict=False):
        if close is None:  # Yahoo leaves gaps as null
            continue
        day = datetime.fromtimestamp(ts, tz=UTC).date()
        bars.append(Bar(day, Decimal(str(close)).quantize(Decimal("0.0001"))))
    return bars
