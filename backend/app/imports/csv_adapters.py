from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pandas as pd


@dataclass
class ParsedImportRow:
    row_index: int
    ticker: str
    name: str | None
    shares: Decimal
    cost_basis: Decimal
    purchase_date: date
    security_type: str
    market: str
    currency: str
    account_name: str | None = None
    brokerage: str | None = None
    cost_basis_source: str = "reported"
    ticker_inferred: bool = False
    review_notes: list[str] = field(default_factory=list)


class CSVImportAdapter:
    name = "generic"
    default_brokerage: str | None = None
    default_security_type = "equity"
    filename_keywords: tuple[str, ...] = ()
    sheet_name_hints: tuple[str, ...] = ("holding", "position", "portfolio", "summary")
    fallback_to_market_value_cost_basis = False
    allow_name_as_ticker = False
    column_aliases = {
        "ticker": ["ticker", "symbol", "security", "investment", "cusip/symbol"],
        "name": ["name", "description", "security name"],
        "shares": ["shares", "quantity", "qty", "units"],
        "cost_basis": ["cost basis", "cost_basis", "book cost", "cost", "total cost", "cost basis total"],
        "average_cost": ["average cost", "avg cost", "cost / share", "cost per share", "average price"],
        "market_value": ["market value", "current value", "value", "balance"],
        "purchase_date": ["purchase date", "acquired", "trade date", "date", "acquired date"],
        "currency": ["currency"],
        "security_type": ["security type", "asset class", "type"],
        "account_name": ["account", "account name"],
        "brokerage": ["brokerage", "custodian"],
    }

    def can_parse(self, filename: str, columns: list[str]) -> bool:
        return Path(filename).suffix.lower() in {".csv", ".xls", ".xlsx", ".xlsm"}

    def parse(self, filename: str, content: bytes) -> tuple[list[ParsedImportRow], list[str]]:
        frame, warnings = self._read_frame(filename, content)
        columns = {self._normalize_label(column): column for column in frame.columns}
        if not self._matches_file(filename, columns):
            raise ValueError("Adapter did not match this file.")

        shares_column = self._resolve_column("shares", columns)
        if shares_column is None:
            raise ValueError("Missing required column for 'shares'")
        if self._resolve_column("ticker", columns) is None and not (
            self.allow_name_as_ticker and self._resolve_column("name", columns) is not None
        ):
            raise ValueError("Missing required column for 'ticker'")

        rows: list[ParsedImportRow] = []
        for idx, record in frame.iterrows():
            ticker, ticker_inferred, ticker_notes = self._resolve_ticker(record, columns)
            if not ticker:
                warnings.append(f"Row {idx + 1}: skipped row without a ticker or investment name")
                continue

            shares = self._parse_decimal(self._value(record, columns, "shares"))
            if shares == Decimal("0"):
                warnings.append(f"Row {idx + 1}: skipped zero-share position for {ticker}")
                continue

            cost_basis, cost_basis_source, cost_basis_notes = self._resolve_cost_basis(record, columns, shares)
            purchase_date_value = self._value(record, columns, "purchase_date")
            purchase_date = self._parse_date(purchase_date_value)
            currency = str(self._value(record, columns, "currency") or "USD").upper()
            market = "india" if currency == "INR" else "us"
            security_type = str(self._value(record, columns, "security_type") or self.default_security_type).lower()
            rows.append(
                ParsedImportRow(
                    row_index=idx + 1,
                    ticker=ticker,
                    name=self._value(record, columns, "name"),
                    shares=shares,
                    cost_basis=cost_basis,
                    purchase_date=purchase_date,
                    security_type=security_type,
                    market=market,
                    currency=currency,
                    account_name=self._value(record, columns, "account_name"),
                    brokerage=self._value(record, columns, "brokerage") or self.default_brokerage,
                    cost_basis_source=cost_basis_source,
                    ticker_inferred=ticker_inferred,
                    review_notes=[*ticker_notes, *cost_basis_notes],
                )
            )
        return rows, warnings

    def _read_frame(self, filename: str, content: bytes) -> tuple[pd.DataFrame, list[str]]:
        suffix = Path(filename).suffix.lower()
        warnings: list[str] = []
        if suffix == ".csv":
            decoded = content.decode("utf-8-sig", errors="ignore")
            rows = list(csv.reader(decoded.splitlines()))
            if not rows:
                raise ValueError("Uploaded file did not contain any rows.")
            width = max(len(row) for row in rows)
            padded = [row + [""] * (width - len(row)) for row in rows]
            raw = pd.DataFrame(padded, dtype=object)
            return self._finalize_frame(raw, warnings, source_label=filename)

        engine = "xlrd" if suffix == ".xls" else "openpyxl"
        workbook = pd.ExcelFile(BytesIO(content), engine=engine)
        sheet_name = self._select_sheet_name(workbook.sheet_names)
        if len(workbook.sheet_names) > 1 and sheet_name != workbook.sheet_names[0]:
            warnings.append(f"Multiple sheets detected. Imported '{sheet_name}' based on brokerage hints.")
        elif len(workbook.sheet_names) > 1:
            warnings.append(f"Multiple sheets detected. Imported the first sheet '{sheet_name}' only.")
        raw = workbook.parse(sheet_name=sheet_name, header=None, dtype=object)
        return self._finalize_frame(raw, warnings, source_label=sheet_name)

    def _finalize_frame(
        self, raw_frame: pd.DataFrame, warnings: list[str], *, source_label: str
    ) -> tuple[pd.DataFrame, list[str]]:
        cleaned = raw_frame.dropna(axis=0, how="all").dropna(axis=1, how="all").reset_index(drop=True)
        if cleaned.empty:
            raise ValueError("Uploaded file did not contain any tabular data.")
        header_index = self._detect_header_row(cleaned)
        if header_index > 0:
            warnings.append(f"Detected a brokerage export preamble. Parsed headers from row {header_index + 1} of {source_label}.")
        header = [
            str(value).strip() if not pd.isna(value) and str(value).strip() else f"column_{position + 1}"
            for position, value in enumerate(cleaned.iloc[header_index].tolist())
        ]
        frame = cleaned.iloc[header_index + 1 :].copy()
        frame.columns = header
        frame = frame.dropna(axis=0, how="all").dropna(axis=1, how="all").reset_index(drop=True)
        return frame, warnings

    def _detect_header_row(self, frame: pd.DataFrame) -> int:
        known_aliases = {
            self._normalize_label(alias)
            for aliases in self.column_aliases.values()
            for alias in aliases
        }
        best_index = 0
        best_score = -1
        sample_size = min(len(frame), 8)
        for index in range(sample_size):
            values = [self._normalize_label(value) for value in frame.iloc[index].tolist() if self._normalize_label(value)]
            score = sum(1 for value in values if value in known_aliases)
            if score > best_score:
                best_index = index
                best_score = score
        return best_index

    def _resolve_column(self, field: str, columns: dict[str, str]) -> str | None:
        for alias in self.column_aliases[field]:
            normalized = self._normalize_label(alias)
            if normalized in columns:
                return columns[normalized]
        return None

    def _value(self, record: pd.Series, columns: dict[str, str], field: str) -> str | None:
        column = self._resolve_column(field, columns)
        if column is None:
            return None
        value = record[column]
        if pd.isna(value):
            return None
        return str(value).strip()

    def _matches_file(self, filename: str, columns: dict[str, str]) -> bool:
        if not self.can_parse(filename, list(columns.keys())):
            return False
        if not self.filename_keywords:
            return True
        lowered_filename = filename.lower()
        if any(keyword in lowered_filename for keyword in self.filename_keywords):
            return True
        return any(self._normalize_label(keyword) in columns for keyword in self.filename_keywords)

    def _select_sheet_name(self, sheet_names: list[str]) -> str:
        lowered = {name: name.lower() for name in sheet_names}
        for hint in self.sheet_name_hints:
            for sheet_name, normalized in lowered.items():
                if hint in normalized:
                    return sheet_name
        return sheet_names[0]

    def _resolve_ticker(
        self, record: pd.Series, columns: dict[str, str]
    ) -> tuple[str | None, bool, list[str]]:
        raw_ticker = self._value(record, columns, "ticker")
        if raw_ticker:
            return self._clean_ticker(raw_ticker), False, []
        raw_name = self._value(record, columns, "name")
        if self.allow_name_as_ticker and raw_name:
            synthetic = self._synthetic_ticker(raw_name)
            return synthetic, True, [f"Ticker inferred from investment name as {synthetic}."]
        return None, False, []

    def _resolve_cost_basis(
        self, record: pd.Series, columns: dict[str, str], shares: Decimal
    ) -> tuple[Decimal, str, list[str]]:
        direct_cost_basis = self._value(record, columns, "cost_basis")
        if direct_cost_basis:
            return self._parse_decimal(direct_cost_basis), "reported", []

        average_cost = self._value(record, columns, "average_cost")
        if average_cost:
            total_cost = (self._parse_decimal(average_cost) * shares).quantize(Decimal("0.0001"))
            return total_cost, "average_cost_inferred", ["Cost basis inferred from average cost per share."]

        market_value = self._value(record, columns, "market_value")
        if self.fallback_to_market_value_cost_basis and market_value:
            return (
                self._parse_decimal(market_value),
                "market_value_fallback",
                ["Used current market value as cost basis because the export did not provide basis data."],
            )

        return Decimal("0"), "missing", ["No cost basis was found. Imported as 0.00."]

    def _parse_date(self, value: str | None) -> date:
        if not value:
            return datetime.utcnow().date()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return pd.to_datetime(value).date()

    def _parse_decimal(self, value: str | None) -> Decimal:
        if not value:
            return Decimal("0")
        normalized = (
            value.replace(",", "")
            .replace("$", "")
            .replace("₹", "")
            .replace("%", "")
            .replace("\u00a0", "")
            .strip()
        )
        if normalized in {"-", "--", ""}:
            return Decimal("0")
        if normalized.startswith("(") and normalized.endswith(")"):
            normalized = f"-{normalized[1:-1]}"
        return Decimal(normalized)

    def _clean_ticker(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9.:-]+", "", value.upper())
        return cleaned

    def _synthetic_ticker(self, name: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", name.upper()).strip("_")
        return f"FUND:{normalized[:28] or 'UNKNOWN'}"

    def _normalize_label(self, value: object) -> str:
        if value is None or pd.isna(value):
            return ""
        return " ".join(str(value).strip().lower().replace("\n", " ").split())


class TaggedCSVImportAdapter(CSVImportAdapter):
    broker_keyword: str = ""

    def can_parse(self, filename: str, columns: list[str]) -> bool:
        lowered = filename.lower()
        normalized_columns = ",".join(columns).lower()
        supported_extension = Path(filename).suffix.lower() in {".csv", ".xls", ".xlsx", ".xlsm"}
        return supported_extension and (
            self.broker_keyword in lowered or self.broker_keyword in normalized_columns
        )


class VanguardCSVImportAdapter(TaggedCSVImportAdapter):
    name = "vanguard_positions"
    broker_keyword = "vanguard"
    default_brokerage = "Vanguard"
    filename_keywords = ("vanguard", "investment name", "cusip/symbol")
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol", "investment symbol", "cusip/symbol"],
        "name": ["name", "investment name", "description"],
        "shares": ["shares", "quantity", "shares/units"],
        "cost_basis": ["cost basis", "book cost", "total cost"],
        "average_cost": ["average cost", "average cost/share"],
        "purchase_date": ["purchase date", "acquired date", "acquired"],
        "account_name": ["account name", "account"],
    }


class FidelityCSVImportAdapter(TaggedCSVImportAdapter):
    name = "fidelity_positions"
    broker_keyword = "fidelity"
    default_brokerage = "Fidelity"
    filename_keywords = ("fidelity", "cost basis total", "account name")
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "shares": ["shares", "quantity", "quantity current"],
        "cost_basis": ["cost basis total", "total cost basis", "cost basis"],
        "average_cost": ["average cost"],
        "account_name": ["account name", "account"],
    }


class RobinhoodCSVImportAdapter(TaggedCSVImportAdapter):
    name = "robinhood_positions"
    broker_keyword = "robinhood"
    default_brokerage = "Robinhood"
    filename_keywords = ("robinhood", "instrument")
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["name", "instrument", "description"],
        "shares": ["shares", "quantity"],
        "average_cost": ["average cost", "average price"],
        "cost_basis": ["cost basis", "total cost"],
        "account_name": ["account", "account name"],
    }


class EmpowerCSVImportAdapter(TaggedCSVImportAdapter):
    name = "empower_retirement"
    broker_keyword = "empower"
    default_brokerage = "Empower"
    default_security_type = "mutual_fund"
    filename_keywords = ("empower", "investment option", "units")
    fallback_to_market_value_cost_basis = True
    allow_name_as_ticker = True
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["investment option", "investment", "fund name", "name"],
        "shares": ["units", "shares", "quantity"],
        "market_value": ["balance", "value", "market value", "current value"],
        "cost_basis": ["cost basis", "book cost"],
        "account_name": ["account name", "plan", "account"],
    }


class PrincipalCSVImportAdapter(TaggedCSVImportAdapter):
    name = "principal_retirement"
    broker_keyword = "principal"
    default_brokerage = "Principal"
    default_security_type = "mutual_fund"
    filename_keywords = ("principal", "investment option", "account balance")
    fallback_to_market_value_cost_basis = True
    allow_name_as_ticker = True
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["investment option", "investment", "fund name", "name"],
        "shares": ["units", "shares", "quantity"],
        "market_value": ["account balance", "balance", "value", "market value"],
        "cost_basis": ["cost basis", "book cost"],
        "account_name": ["account name", "plan name", "account"],
    }


class Slavic401kCSVImportAdapter(TaggedCSVImportAdapter):
    name = "slavic_401k_positions"
    broker_keyword = "slavic"
    default_brokerage = "Slavic 401k"
    default_security_type = "mutual_fund"
    filename_keywords = ("slavic", "investment option", "share balance")
    fallback_to_market_value_cost_basis = True
    allow_name_as_ticker = True
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["investment option", "investment", "fund name", "name"],
        "shares": ["share balance", "units", "shares", "quantity"],
        "market_value": ["balance", "value", "market value", "account balance"],
        "cost_basis": ["cost basis", "book cost"],
        "account_name": ["account name", "plan", "account"],
    }


class SchwabCSVImportAdapter(TaggedCSVImportAdapter):
    name = "schwab_positions"
    broker_keyword = "schwab"
    default_brokerage = "Schwab"
    filename_keywords = ("schwab", "charles schwab", "cost basis")
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["name", "description"],
        "shares": ["shares", "quantity"],
        "cost_basis": ["cost basis", "total cost"],
        "average_cost": ["average cost", "cost / share"],
        "market_value": ["market value", "market value ($)"],
        "account_name": ["account name", "account"],
    }


class WealthfrontCSVImportAdapter(TaggedCSVImportAdapter):
    name = "wealthfront_positions"
    broker_keyword = "wealthfront"
    default_brokerage = "Wealthfront"
    filename_keywords = ("wealthfront", "average price")
    column_aliases = {
        **CSVImportAdapter.column_aliases,
        "ticker": ["ticker", "symbol"],
        "name": ["name", "description"],
        "shares": ["shares", "quantity"],
        "average_cost": ["average price", "average cost"],
        "cost_basis": ["cost basis", "total cost"],
        "account_name": ["account", "account name", "portfolio"],
    }


ADAPTERS = [
    VanguardCSVImportAdapter(),
    FidelityCSVImportAdapter(),
    RobinhoodCSVImportAdapter(),
    EmpowerCSVImportAdapter(),
    PrincipalCSVImportAdapter(),
    Slavic401kCSVImportAdapter(),
    SchwabCSVImportAdapter(),
    WealthfrontCSVImportAdapter(),
    CSVImportAdapter(),
]
