from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from math import sin

import httpx

from app.core.config import get_settings


@dataclass
class QuoteResult:
    ticker: str
    price: Decimal
    currency: str
    as_of: date
    source: str
    dividend_yield: Decimal | None = None


@dataclass
class HistoryResult:
    ticker: str
    points: list[tuple[date, Decimal]]
    currency: str
    source: str


class FallbackMarketDataProvider:
    def _seed(self, ticker: str) -> int:
        return int(sha256(ticker.encode("utf-8")).hexdigest()[:8], 16)

    def _base_price(self, ticker: str, reference_price: Decimal | None = None) -> Decimal:
        if reference_price and reference_price > 0:
            return reference_price
        seed = self._seed(ticker)
        return Decimal(str(25 + (seed % 275)))

    def get_quote(
        self, ticker: str, currency: str = "USD", reference_price: Decimal | None = None
    ) -> QuoteResult:
        base = self._base_price(ticker, reference_price)
        drift = Decimal(str(((self._seed(ticker) % 31) - 10) / 100))
        price = (base * (Decimal("1") + drift)).quantize(Decimal("0.0001"))
        dividend = (Decimal(str((self._seed(ticker) % 8) / 100)) if currency == "USD" else Decimal("0"))
        return QuoteResult(
            ticker=ticker,
            price=price,
            currency=currency,
            as_of=datetime.now(timezone.utc).date(),
            source="fallback",
            dividend_yield=dividend,
        )

    def get_history(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        currency: str = "USD",
        reference_price: Decimal | None = None,
    ) -> HistoryResult:
        base = self._base_price(ticker, reference_price)
        seed = self._seed(ticker)
        points: list[tuple[date, Decimal]] = []
        current = start_date
        while current <= end_date:
            day_index = (current - start_date).days
            trend = Decimal(str(((seed % 17) - 8) / 500))
            seasonal = Decimal(str(sin((day_index + (seed % 23)) / 9) / 18))
            price = (base * (Decimal("1") + trend * Decimal(day_index) + seasonal)).quantize(
                Decimal("0.0001")
            )
            points.append((current, max(price, Decimal("1"))))
            current += timedelta(days=1)
        return HistoryResult(ticker=ticker, points=points, currency=currency, source="fallback")

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        if from_currency == to_currency:
            return Decimal("1")
        if from_currency == "INR" and to_currency == "USD":
            return Decimal("0.0120")
        if from_currency == "USD" and to_currency == "INR":
            return Decimal("83.3333")
        return Decimal("1")


class FinnhubProvider:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"

    def get_quote(self, ticker: str) -> QuoteResult | None:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{self.base_url}/quote",
                params={"symbol": ticker, "token": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
        price = payload.get("c")
        if not price:
            return None
        return QuoteResult(
            ticker=ticker,
            price=Decimal(str(price)),
            currency="USD",
            as_of=datetime.now(timezone.utc).date(),
            source="finnhub",
        )

    def get_history(self, ticker: str, start_date: date, end_date: date) -> HistoryResult | None:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{self.base_url}/stock/candle",
                params={
                    "symbol": ticker,
                    "resolution": "D",
                    "from": int(
                        datetime.combine(start_date, datetime.min.time(), timezone.utc).timestamp()
                    ),
                    "to": int(
                        datetime.combine(end_date, datetime.min.time(), timezone.utc).timestamp()
                    ),
                    "token": self.api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("s") != "ok":
            return None
        points = [
            (datetime.fromtimestamp(ts, timezone.utc).date(), Decimal(str(close)))
            for ts, close in zip(payload.get("t", []), payload.get("c", []), strict=False)
        ]
        return HistoryResult(ticker=ticker, points=points, currency="USD", source="finnhub")


class AlphaVantageProvider:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"

    def get_dividend_yield(self, ticker: str) -> Decimal | None:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                self.base_url,
                params={"function": "OVERVIEW", "symbol": ticker, "apikey": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
        raw_yield = payload.get("DividendYield")
        if raw_yield in (None, "", "None"):
            return None
        return Decimal(str(raw_yield))


class FrankfurterFxProvider:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get_rate(self, from_currency: str, to_currency: str) -> Decimal | None:
        if from_currency == to_currency:
            return Decimal("1")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{self.base_url}/latest", params={"from": from_currency, "to": to_currency}
            )
            response.raise_for_status()
            payload = response.json()
        rate = payload.get("rates", {}).get(to_currency)
        if rate is None:
            return None
        return Decimal(str(rate))


class MarketDataRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self.fallback = FallbackMarketDataProvider()
        self.finnhub = FinnhubProvider(settings.finnhub_api_key) if settings.finnhub_api_key else None
        self.alpha_vantage = (
            AlphaVantageProvider(settings.alpha_vantage_api_key)
            if settings.alpha_vantage_api_key
            else None
        )
        self.fx_provider = FrankfurterFxProvider(settings.fx_api_base_url)

    def quote(
        self, ticker: str, currency: str = "USD", reference_price: Decimal | None = None
    ) -> QuoteResult:
        try:
            if currency == "USD" and self.finnhub:
                result = self.finnhub.get_quote(ticker)
                if result:
                    if self.alpha_vantage:
                        result.dividend_yield = self.alpha_vantage.get_dividend_yield(ticker)
                    return result
        except Exception:
            pass
        return self.fallback.get_quote(ticker, currency=currency, reference_price=reference_price)

    def history(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        currency: str = "USD",
        reference_price: Decimal | None = None,
    ) -> HistoryResult:
        try:
            if currency == "USD" and self.finnhub:
                result = self.finnhub.get_history(ticker, start_date, end_date)
                if result and result.points:
                    return result
        except Exception:
            pass
        return self.fallback.get_history(
            ticker, start_date, end_date, currency=currency, reference_price=reference_price
        )

    def fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        try:
            rate = self.fx_provider.get_rate(from_currency, to_currency)
            if rate:
                return rate
        except Exception:
            pass
        return self.fallback.get_fx_rate(from_currency, to_currency)
