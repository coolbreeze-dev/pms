from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import uuid4

from app.core.brokerages import normalize_brokerage
from app.core.config import Settings


DECIMAL_ZERO = Decimal("0")


class BrokerageSyncProviderError(RuntimeError):
    pass


class BrokerageSyncConfigurationError(BrokerageSyncProviderError):
    pass


@dataclass
class SyncUserCredentials:
    external_user_id: str
    external_user_secret: str


@dataclass
class ConnectionPortal:
    url: str
    expires_at: datetime | None = None


@dataclass
class SyncedHoldingPayload:
    ticker: str
    shares: Decimal
    cost_basis: Decimal
    purchase_date: date
    currency: str = "USD"
    name: str | None = None
    security_type: str = "equity"
    market: str = "us"
    external_id: str | None = None


@dataclass
class SyncedTransactionPayload:
    external_id: str
    ticker: str
    transaction_type: str
    shares: Decimal
    price_per_share: Decimal
    total_amount: Decimal
    transaction_date: date
    notes: str | None = None


@dataclass
class SyncedAccountPayload:
    external_id: str
    name: str
    account_type: str
    brokerage: str
    category: str
    currency: str = "USD"
    authorization_id: str | None = None
    holdings: list[SyncedHoldingPayload] = field(default_factory=list)
    cash_transactions: list[SyncedTransactionPayload] = field(default_factory=list)


class BrokerageSyncProvider(Protocol):
    name: str
    label: str

    def is_configured(self) -> bool:
        ...

    def setup_instructions(self) -> str | None:
        ...

    def ensure_user(
        self, *, local_profile_id: str, existing_external_user_id: str | None = None
    ) -> SyncUserCredentials:
        ...

    def create_connection_portal(self, credentials: SyncUserCredentials) -> ConnectionPortal:
        ...

    def sync_accounts(
        self, credentials: SyncUserCredentials, *, activity_lookback_days: int
    ) -> list[SyncedAccountPayload]:
        ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _as_date(value: Any, fallback: date | None = None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return fallback or date.today()
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
        except ValueError:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(cleaned, fmt).date()
                except ValueError:
                    continue
    return fallback or date.today()


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _extract(data: dict[str, Any] | None, *keys: str) -> Any:
    if not data:
        return None
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _coerce_body(response: Any) -> Any:
    if hasattr(response, "body"):
        return response.body
    return response


def _coerce_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "accounts", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return [payload]


def infer_account_category(account_type: str, currency: str, brokerage: str) -> str:
    normalized_type = account_type.lower()
    normalized_brokerage = brokerage.lower()
    if currency.upper() == "INR" or "india" in normalized_brokerage:
        return "india"
    retirement_keywords = ("401", "403", "457", "ira", "roth", "retirement", "pension", "sep", "simple")
    if any(keyword in normalized_type for keyword in retirement_keywords):
        return "retirement"
    return "brokerage"


def map_activity_type(raw_type: str) -> str | None:
    normalized = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
    if any(token in normalized for token in ("dividend", "distribution")):
        return "dividend"
    if any(token in normalized for token in ("deposit", "contribution", "transfer_in", "cash_in")):
        return "deposit"
    if any(token in normalized for token in ("withdraw", "transfer_out", "cash_out", "fee")):
        return "withdrawal"
    return None


class DisabledBrokerageSyncProvider:
    name = "disabled"
    label = "Brokerage Sync"

    def is_configured(self) -> bool:
        return False

    def setup_instructions(self) -> str | None:
        return "Set BROKERAGE_SYNC_PROVIDER=snaptrade and configure SnapTrade credentials to enable brokerage sync."

    def ensure_user(
        self, *, local_profile_id: str, existing_external_user_id: str | None = None
    ) -> SyncUserCredentials:
        raise BrokerageSyncConfigurationError(self.setup_instructions() or "Brokerage sync is disabled.")

    def create_connection_portal(self, credentials: SyncUserCredentials) -> ConnectionPortal:
        raise BrokerageSyncConfigurationError(self.setup_instructions() or "Brokerage sync is disabled.")

    def sync_accounts(
        self, credentials: SyncUserCredentials, *, activity_lookback_days: int
    ) -> list[SyncedAccountPayload]:
        raise BrokerageSyncConfigurationError(self.setup_instructions() or "Brokerage sync is disabled.")


class MockBrokerageSyncProvider:
    name = "mock"
    label = "Mock Brokerage Sync"

    def is_configured(self) -> bool:
        return True

    def setup_instructions(self) -> str | None:
        return None

    def ensure_user(
        self, *, local_profile_id: str, existing_external_user_id: str | None = None
    ) -> SyncUserCredentials:
        user_id = existing_external_user_id or f"{local_profile_id}-{uuid4().hex[:8]}"
        return SyncUserCredentials(external_user_id=user_id, external_user_secret=f"secret-{user_id}")

    def create_connection_portal(self, credentials: SyncUserCredentials) -> ConnectionPortal:
        expires_at = _utcnow() + timedelta(minutes=15)
        return ConnectionPortal(
            url=f"https://example.test/sync/connect/{credentials.external_user_id}",
            expires_at=expires_at,
        )

    def sync_accounts(
        self, credentials: SyncUserCredentials, *, activity_lookback_days: int
    ) -> list[SyncedAccountPayload]:
        today = date.today()
        return [
            SyncedAccountPayload(
                external_id="mock-taxable-001",
                authorization_id="mock-auth-001",
                name="Wealthfront Taxable",
                account_type="Individual Brokerage",
                brokerage="Wealthfront",
                category="brokerage",
                holdings=[
                    SyncedHoldingPayload(
                        external_id="mock-taxable-vti",
                        ticker="VTI",
                        name="Vanguard Total Stock Market ETF",
                        shares=Decimal("12.50000000"),
                        cost_basis=Decimal("3145.2500"),
                        purchase_date=today - timedelta(days=420),
                    ),
                    SyncedHoldingPayload(
                        external_id="mock-taxable-vxus",
                        ticker="VXUS",
                        name="Vanguard Total International Stock ETF",
                        shares=Decimal("8.10000000"),
                        cost_basis=Decimal("465.0000"),
                        purchase_date=today - timedelta(days=200),
                    ),
                ],
                cash_transactions=[
                    SyncedTransactionPayload(
                        external_id="mock-taxable-deposit-001",
                        ticker="CASH",
                        transaction_type="deposit",
                        shares=DECIMAL_ZERO,
                        price_per_share=DECIMAL_ZERO,
                        total_amount=Decimal("750.0000"),
                        transaction_date=today - timedelta(days=14),
                        notes="Mock brokerage transfer",
                    ),
                    SyncedTransactionPayload(
                        external_id="mock-taxable-dividend-001",
                        ticker="VTI",
                        transaction_type="dividend",
                        shares=DECIMAL_ZERO,
                        price_per_share=DECIMAL_ZERO,
                        total_amount=Decimal("18.4200"),
                        transaction_date=today - timedelta(days=7),
                        notes="Mock quarterly dividend",
                    ),
                ],
            ),
            SyncedAccountPayload(
                external_id="mock-retirement-001",
                authorization_id="mock-auth-002",
                name="Principal 401k",
                account_type="401k",
                brokerage="Principal",
                category="retirement",
                holdings=[
                    SyncedHoldingPayload(
                        external_id="mock-retirement-voo",
                        ticker="VOO",
                        name="Vanguard S&P 500 ETF",
                        shares=Decimal("22.00000000"),
                        cost_basis=Decimal("9050.0000"),
                        purchase_date=today - timedelta(days=600),
                    )
                ],
                cash_transactions=[
                    SyncedTransactionPayload(
                        external_id="mock-retirement-deposit-001",
                        ticker="CASH",
                        transaction_type="deposit",
                        shares=DECIMAL_ZERO,
                        price_per_share=DECIMAL_ZERO,
                        total_amount=Decimal("1200.0000"),
                        transaction_date=today - timedelta(days=30),
                        notes="Mock employer contribution",
                    )
                ],
            ),
        ]


class SnapTradeBrokerageSyncProvider:
    name = "snaptrade"
    label = "SnapTrade"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._sdk_error: str | None = None

    def is_configured(self) -> bool:
        return bool(
            self._settings.snaptrade_client_id
            and self._settings.snaptrade_consumer_key
            and self._import_error() is None
        )

    def setup_instructions(self) -> str | None:
        has_credentials = bool(self._settings.snaptrade_client_id and self._settings.snaptrade_consumer_key)
        if not has_credentials:
            return (
                "Set SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, and BROKERAGE_SYNC_PROVIDER=snaptrade "
                "to enable live brokerage sync."
            )
        if self._import_error() is not None:
            return "Install the optional SnapTrade SDK with `backend/.venv/bin/pip install '.[brokerage-sync]'`."
        return None

    def ensure_user(
        self, *, local_profile_id: str, existing_external_user_id: str | None = None
    ) -> SyncUserCredentials:
        client = self._client()
        if existing_external_user_id:
            raise BrokerageSyncConfigurationError(
                "A stored SnapTrade user is required to continue. Reconnect from Settings if this user was lost."
            )
        user_id = f"{local_profile_id}-{uuid4().hex[:12]}"
        response = client.authentication.register_snap_trade_user(body={"userId": user_id})
        body = _coerce_body(response)
        user_secret = _extract(body, "userSecret", "user_secret")
        if not user_secret:
            raise BrokerageSyncProviderError("SnapTrade did not return a user secret.")
        return SyncUserCredentials(external_user_id=user_id, external_user_secret=str(user_secret))

    def create_connection_portal(self, credentials: SyncUserCredentials) -> ConnectionPortal:
        client = self._client()
        response = client.authentication.login_snap_trade_user(
            query_params={
                "userId": credentials.external_user_id,
                "userSecret": credentials.external_user_secret,
                **({"redirectUri": self._settings.snaptrade_redirect_uri} if self._settings.snaptrade_redirect_uri else {}),
            }
        )
        body = _coerce_body(response)
        url = _extract(body, "redirectURI", "redirectUri", "url")
        if not url:
            raise BrokerageSyncProviderError("SnapTrade did not return a connection portal URL.")
        expires_at = _as_datetime(_extract(body, "sessionExpiry", "expiresAt", "expires_at"))
        return ConnectionPortal(url=str(url), expires_at=expires_at)

    def sync_accounts(
        self, credentials: SyncUserCredentials, *, activity_lookback_days: int
    ) -> list[SyncedAccountPayload]:
        client = self._client()
        response = client.account_information.get_all_user_holdings(
            query_params={
                "userId": credentials.external_user_id,
                "userSecret": credentials.external_user_secret,
            }
        )
        bundles = _coerce_list(_coerce_body(response))
        synced_accounts: list[SyncedAccountPayload] = []

        for bundle in bundles:
            if not isinstance(bundle, dict):
                continue
            account_payload = bundle.get("account") if isinstance(bundle.get("account"), dict) else bundle
            account_id = _extract(account_payload, "id", "accountId", "account_id")
            if not account_id:
                continue

            account_type = str(_extract(account_payload, "type", "account_type", "accountType") or "Brokerage")
            currency = str(_extract(account_payload, "currency", "base_currency") or "USD").upper()
            brokerage = normalize_brokerage(
                str(
                    _extract(
                        account_payload,
                        "institution_name",
                        "institutionName",
                        "institution",
                        "brokerage",
                    )
                    or "Brokerage"
                )
            )
            account = SyncedAccountPayload(
                external_id=str(account_id),
                authorization_id=(
                    str(
                        _extract(
                            account_payload,
                            "brokerage_authorization",
                            "brokerageAuthorization",
                            "authorizationId",
                            "brokerage_authorization_id",
                        )
                    )
                    if _extract(
                        account_payload,
                        "brokerage_authorization",
                        "brokerageAuthorization",
                        "authorizationId",
                        "brokerage_authorization_id",
                    )
                    is not None
                    else None
                ),
                name=str(_extract(account_payload, "name", "display_name", "displayName") or f"{brokerage} {account_type}"),
                account_type=account_type,
                brokerage=brokerage,
                category=infer_account_category(account_type, currency, brokerage),
                currency=currency,
                holdings=self._parse_positions(bundle.get("positions") or bundle.get("holdings"), currency=currency),
                cash_transactions=self._get_cash_transactions(
                    client,
                    credentials=credentials,
                    account_id=str(account_id),
                    activity_lookback_days=activity_lookback_days,
                ),
            )
            synced_accounts.append(account)

        return synced_accounts

    def _parse_positions(self, positions_payload: Any, *, currency: str) -> list[SyncedHoldingPayload]:
        positions: list[SyncedHoldingPayload] = []
        for position in _coerce_list(positions_payload):
            if not isinstance(position, dict):
                continue
            raw_symbol = position.get("symbol")
            ticker = ""
            if isinstance(raw_symbol, dict):
                ticker = str(_extract(raw_symbol, "symbol", "ticker", "id") or "").upper()
            elif raw_symbol is not None:
                ticker = str(raw_symbol).upper()
            if not ticker:
                ticker = str(_extract(position, "ticker", "id") or "").upper()
            if not ticker:
                continue

            shares = _as_decimal(_extract(position, "units", "quantity", "shares"))
            if shares <= DECIMAL_ZERO:
                continue
            avg_cost = _as_decimal(_extract(position, "average_purchase_price", "averagePrice", "average_price"))
            cost_basis = (avg_cost * shares).quantize(Decimal("0.0001"))
            description = _extract(position, "description", "name")
            security_type = str(_extract(position, "type", "asset_class", "security_type") or "equity")
            purchase_date = _as_date(_extract(position, "last_investment_transaction", "purchase_date"))
            positions.append(
                SyncedHoldingPayload(
                    external_id=(
                        str(_extract(position, "id", "positionId", "position_id"))
                        if _extract(position, "id", "positionId", "position_id") is not None
                        else None
                    ),
                    ticker=ticker,
                    name=str(description) if description is not None else None,
                    shares=shares.quantize(Decimal("0.00000001")),
                    cost_basis=cost_basis,
                    purchase_date=purchase_date,
                    currency=str(_extract(position, "currency") or currency).upper(),
                    market="india" if str(_extract(position, "currency") or currency).upper() == "INR" else "us",
                    security_type=security_type.lower(),
                )
            )
        return positions

    def _get_cash_transactions(
        self,
        client: Any,
        *,
        credentials: SyncUserCredentials,
        account_id: str,
        activity_lookback_days: int,
    ) -> list[SyncedTransactionPayload]:
        start_date = (date.today() - timedelta(days=activity_lookback_days)).isoformat()
        query_params = {
            "userId": credentials.external_user_id,
            "userSecret": credentials.external_user_secret,
            "startDate": start_date,
            "endDate": date.today().isoformat(),
        }
        try:
            response = client.account_information.get_account_activities(account_id, query_params=query_params)
        except TypeError:
            response = client.account_information.get_account_activities(
                query_params={**query_params, "accountId": account_id}
            )
        activities = _coerce_list(_coerce_body(response))
        results: list[SyncedTransactionPayload] = []
        for activity in activities:
            normalized = self._normalize_activity(activity)
            if normalized is not None:
                results.append(normalized)
        return results

    def _normalize_activity(self, activity: Any) -> SyncedTransactionPayload | None:
        if not isinstance(activity, dict):
            return None
        mapped_type = map_activity_type(
            str(
                _extract(
                    activity,
                    "type",
                    "activityType",
                    "description",
                    "display_name",
                )
                or ""
            )
        )
        if mapped_type is None:
            return None

        symbol = _extract(activity, "symbol", "ticker") or "CASH"
        if isinstance(symbol, dict):
            symbol = _extract(symbol, "symbol", "ticker", "id") or "CASH"
        amount = _as_decimal(_extract(activity, "amount", "netAmount", "net_amount"))
        shares = _as_decimal(_extract(activity, "units", "quantity", "shares"))
        price = _as_decimal(_extract(activity, "price", "price_per_share", "pricePerShare"))
        if price == DECIMAL_ZERO and shares > DECIMAL_ZERO and amount > DECIMAL_ZERO:
            price = (amount / shares).quantize(Decimal("0.00000001"))
        transaction_date = _as_date(
            _extract(activity, "tradeDate", "date", "activityDate", "settlementDate"),
            fallback=date.today(),
        )
        external_id = _extract(activity, "id", "activityId", "transactionId")
        if external_id is None:
            external_id = (
                f"{mapped_type}:{transaction_date.isoformat()}:{str(symbol).upper()}:{amount.normalize()}"
            )
        notes = _extract(activity, "description", "display_name", "memo")
        return SyncedTransactionPayload(
            external_id=str(external_id),
            ticker=str(symbol).upper(),
            transaction_type=mapped_type,
            shares=shares.quantize(Decimal("0.00000001")),
            price_per_share=price.quantize(Decimal("0.00000001")),
            total_amount=amount.quantize(Decimal("0.0001")),
            transaction_date=transaction_date,
            notes=str(notes) if notes is not None else None,
        )

    def _client(self) -> Any:
        if not self.is_configured():
            raise BrokerageSyncConfigurationError(self.setup_instructions() or "SnapTrade is not configured.")
        try:
            from snaptrade_client import SnapTrade
        except ImportError as exc:
            self._sdk_error = str(exc)
            raise BrokerageSyncConfigurationError(self.setup_instructions() or "SnapTrade SDK is unavailable.") from exc
        return SnapTrade(
            clientId=self._settings.snaptrade_client_id,
            consumerKey=self._settings.snaptrade_consumer_key,
        )

    def _import_error(self) -> str | None:
        try:
            import snaptrade_client  # noqa: F401
        except ImportError as exc:
            return str(exc)
        return None


def get_brokerage_sync_provider(settings: Settings) -> BrokerageSyncProvider:
    provider_name = settings.brokerage_sync_provider.lower().strip()
    if provider_name == "mock":
        return MockBrokerageSyncProvider()
    if provider_name == "snaptrade":
        return SnapTradeBrokerageSyncProvider(settings)
    return DisabledBrokerageSyncProvider()
