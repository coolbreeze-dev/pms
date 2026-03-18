from enum import Enum


class AccountCategory(str, Enum):
    BROKERAGE = "brokerage"
    RETIREMENT = "retirement"
    INDIA = "india"


class SecurityType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    CRYPTO = "crypto"
    CASH = "cash"


class ImportJobStatus(str, Enum):
    PREVIEWED = "previewed"
    COMMITTED = "committed"
    FAILED = "failed"


class BackgroundJobType(str, Enum):
    REFRESH_PRICES = "refresh_prices"


class BackgroundJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

