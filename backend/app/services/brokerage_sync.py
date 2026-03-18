from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.brokerages import normalize_brokerage
from app.core.config import get_settings
from app.models import Account, BrokerageSyncUser, Holding, Transaction
from app.providers.brokerage_sync import (
    BrokerageSyncConfigurationError,
    BrokerageSyncProviderError,
    SyncedAccountPayload,
    SyncedHoldingPayload,
    SyncedTransactionPayload,
    SyncUserCredentials,
    get_brokerage_sync_provider,
)
from app.schemas.api import (
    BrokerageSyncConnectResponse,
    BrokerageSyncRunResponse,
    BrokerageSyncStatusResponse,
    BrokerageSyncUserRead,
    BrokerageSyncedAccountRead,
)


DECIMAL_ZERO = Decimal("0")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _provider():
    settings = get_settings()
    return settings, get_brokerage_sync_provider(settings)


def _serialize_user(sync_user: BrokerageSyncUser) -> BrokerageSyncUserRead:
    return BrokerageSyncUserRead(
        provider=sync_user.provider,
        local_profile_id=sync_user.local_profile_id,
        external_user_id=sync_user.external_user_id,
        status=sync_user.status,
        last_synced_at=sync_user.last_synced_at,
        last_error=sync_user.last_error,
        last_portal_expires_at=sync_user.last_portal_expires_at,
        created_at=sync_user.created_at,
    )


def _get_sync_user(session: Session, provider_name: str, local_profile_id: str) -> BrokerageSyncUser | None:
    return session.scalar(
        select(BrokerageSyncUser).where(
            BrokerageSyncUser.provider == provider_name,
            BrokerageSyncUser.local_profile_id == local_profile_id,
        )
    )


def _require_provider():
    settings, provider = _provider()
    if not settings.brokerage_sync_enabled:
        raise HTTPException(status_code=400, detail=provider.setup_instructions() or "Brokerage sync is disabled.")
    if not provider.is_configured():
        raise HTTPException(status_code=400, detail=provider.setup_instructions() or "Brokerage sync is not configured.")
    return settings, provider


def _ensure_sync_user(session: Session) -> tuple[BrokerageSyncUser, bool]:
    settings, provider = _require_provider()
    sync_user = _get_sync_user(session, provider.name, settings.brokerage_sync_local_profile_id)
    if sync_user is not None:
        return sync_user, False

    try:
        credentials = provider.ensure_user(local_profile_id=settings.brokerage_sync_local_profile_id)
    except (BrokerageSyncConfigurationError, BrokerageSyncProviderError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    sync_user = BrokerageSyncUser(
        provider=provider.name,
        local_profile_id=settings.brokerage_sync_local_profile_id,
        external_user_id=credentials.external_user_id,
        external_user_secret=credentials.external_user_secret,
        status="linked",
        metadata_json={},
    )
    session.add(sync_user)
    session.commit()
    session.refresh(sync_user)
    return sync_user, True


def _credentials(sync_user: BrokerageSyncUser) -> SyncUserCredentials:
    return SyncUserCredentials(
        external_user_id=sync_user.external_user_id,
        external_user_secret=sync_user.external_user_secret,
    )


def get_brokerage_sync_status(session: Session) -> BrokerageSyncStatusResponse:
    settings, provider = _provider()
    sync_user = _get_sync_user(session, provider.name, settings.brokerage_sync_local_profile_id)
    synced_accounts = session.scalars(
        select(Account)
        .where(Account.sync_provider == provider.name)
        .order_by(Account.brokerage.asc(), Account.name.asc())
    ).all()

    account_rows: list[BrokerageSyncedAccountRead] = []
    total_synced_holdings = 0
    total_synced_transactions = 0

    for account in synced_accounts:
        holdings_count = (
            session.scalar(
                select(func.count()).select_from(Holding).where(
                    Holding.account_id == account.id, Holding.sync_provider == provider.name
                )
            )
            or 0
        )
        transactions_count = (
            session.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.account_id == account.id, Transaction.sync_provider == provider.name
                )
            )
            or 0
        )
        total_synced_holdings += holdings_count
        total_synced_transactions += transactions_count
        account_rows.append(
            BrokerageSyncedAccountRead(
                account_id=account.id,
                account_name=account.name,
                brokerage=account.brokerage,
                account_type=account.account_type,
                category=account.category,
                sync_status=account.sync_status,
                last_synced_at=account.last_synced_at,
                last_sync_error=account.last_sync_error,
                holdings_count=holdings_count,
                cash_transactions_count=transactions_count,
            )
        )

    return BrokerageSyncStatusResponse(
        provider=provider.name,
        provider_label=provider.label,
        enabled=settings.brokerage_sync_enabled,
        configured=provider.is_configured(),
        setup_instructions=provider.setup_instructions(),
        user=_serialize_user(sync_user) if sync_user else None,
        synced_accounts=account_rows,
        total_synced_holdings=total_synced_holdings,
        total_synced_transactions=total_synced_transactions,
    )


def create_brokerage_connect_portal(session: Session) -> BrokerageSyncConnectResponse:
    settings, provider = _require_provider()
    sync_user, user_created = _ensure_sync_user(session)
    try:
        portal = provider.create_connection_portal(_credentials(sync_user))
    except (BrokerageSyncConfigurationError, BrokerageSyncProviderError) as exc:
        sync_user.last_error = str(exc)
        session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    sync_user.last_portal_url = portal.url
    sync_user.last_portal_expires_at = portal.expires_at
    sync_user.last_error = None
    session.commit()
    session.refresh(sync_user)
    return BrokerageSyncConnectResponse(
        provider=provider.name,
        provider_label=provider.label,
        portal_url=portal.url,
        expires_at=portal.expires_at,
        user_created=user_created,
        user=_serialize_user(sync_user),
    )


def run_brokerage_sync(session: Session) -> BrokerageSyncRunResponse:
    settings, provider = _require_provider()
    sync_user = _get_sync_user(session, provider.name, settings.brokerage_sync_local_profile_id)
    if sync_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start by opening the brokerage connection portal from Settings.",
        )

    sync_started_at = _utcnow()
    try:
        synced_accounts = provider.sync_accounts(
            _credentials(sync_user),
            activity_lookback_days=settings.brokerage_sync_activity_lookback_days,
        )
    except (BrokerageSyncConfigurationError, BrokerageSyncProviderError) as exc:
        sync_user.status = "error"
        sync_user.last_error = str(exc)
        session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    accounts_synced = 0
    holdings_synced = 0
    transactions_synced = 0
    warnings: list[str] = []

    for synced_account in synced_accounts:
        try:
            account, account_holding_count, account_transaction_count = _upsert_synced_account(
                session,
                provider_name=provider.name,
                synced_account=synced_account,
                synced_at=sync_started_at,
            )
        except Exception as exc:  # pragma: no cover - defensive guard for provider payload mismatches
            warnings.append(f"Skipped account {synced_account.name}: {exc}")
            continue

        accounts_synced += 1
        holdings_synced += account_holding_count
        transactions_synced += account_transaction_count
        account.sync_status = "synced"
        account.last_synced_at = sync_started_at
        account.last_sync_error = None

    sync_user.status = "synced"
    sync_user.last_synced_at = sync_started_at
    sync_user.last_error = None
    session.commit()

    return BrokerageSyncRunResponse(
        provider=provider.name,
        provider_label=provider.label,
        status="completed",
        synced_at=sync_started_at,
        accounts_synced=accounts_synced,
        holdings_synced=holdings_synced,
        cash_transactions_synced=transactions_synced,
        warnings=warnings,
    )


def _upsert_synced_account(
    session: Session,
    *,
    provider_name: str,
    synced_account: SyncedAccountPayload,
    synced_at: datetime,
) -> tuple[Account, int, int]:
    account = session.scalar(
        select(Account).where(
            Account.sync_provider == provider_name,
            Account.sync_external_id == synced_account.external_id,
        )
    )
    if account is None:
        account = Account(
            name=synced_account.name,
            account_type=synced_account.account_type,
            category=synced_account.category,
            brokerage=normalize_brokerage(synced_account.brokerage),
            sync_provider=provider_name,
            sync_external_id=synced_account.external_id,
            sync_authorization_id=synced_account.authorization_id,
            sync_status="pending",
        )
        session.add(account)
        session.flush()
    else:
        account.name = synced_account.name
        account.account_type = synced_account.account_type
        account.category = synced_account.category
        account.brokerage = normalize_brokerage(synced_account.brokerage)
        account.sync_authorization_id = synced_account.authorization_id

    holding_count = _replace_account_holdings(
        session,
        account_id=account.id,
        provider_name=provider_name,
        holdings=synced_account.holdings,
        synced_at=synced_at,
    )
    transaction_count = _upsert_cash_transactions(
        session,
        account_id=account.id,
        provider_name=provider_name,
        transactions=synced_account.cash_transactions,
        synced_at=synced_at,
    )
    return account, holding_count, transaction_count


def _replace_account_holdings(
    session: Session,
    *,
    account_id: int,
    provider_name: str,
    holdings: list[SyncedHoldingPayload],
    synced_at: datetime,
) -> int:
    existing_holdings = session.scalars(select(Holding).where(Holding.account_id == account_id)).all()
    for holding in existing_holdings:
        session.delete(holding)
    session.flush()

    inserted = 0
    for holding in holdings:
        cost_basis_per_share = (
            (holding.cost_basis / holding.shares).quantize(Decimal("0.00000001"))
            if holding.shares > DECIMAL_ZERO
            else DECIMAL_ZERO
        )
        session.add(
            Holding(
                account_id=account_id,
                ticker=holding.ticker.upper(),
                name=holding.name,
                shares=holding.shares.quantize(Decimal("0.00000001")),
                cost_basis=holding.cost_basis.quantize(Decimal("0.0001")),
                cost_basis_per_share=cost_basis_per_share,
                purchase_date=holding.purchase_date,
                security_type=holding.security_type,
                market=holding.market,
                currency=holding.currency.upper(),
                import_source=f"{provider_name}:sync",
                sync_provider=provider_name,
                sync_external_id=holding.external_id,
                synced_at=synced_at,
            )
        )
        inserted += 1
    session.flush()
    return inserted


def _upsert_cash_transactions(
    session: Session,
    *,
    account_id: int,
    provider_name: str,
    transactions: list[SyncedTransactionPayload],
    synced_at: datetime,
) -> int:
    upserted = 0
    for payload in transactions:
        transaction = session.scalar(
            select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.sync_provider == provider_name,
                Transaction.sync_external_id == payload.external_id,
            )
        )
        if transaction is None:
            transaction = Transaction(
                account_id=account_id,
                ticker=payload.ticker.upper(),
                transaction_type=payload.transaction_type,
                shares=payload.shares.quantize(Decimal("0.00000001")),
                price_per_share=payload.price_per_share.quantize(Decimal("0.00000001")),
                total_amount=payload.total_amount.quantize(Decimal("0.0001")),
                transaction_date=payload.transaction_date,
                notes=payload.notes,
                sync_provider=provider_name,
                sync_external_id=payload.external_id,
                synced_at=synced_at,
            )
            session.add(transaction)
        else:
            transaction.ticker = payload.ticker.upper()
            transaction.transaction_type = payload.transaction_type
            transaction.shares = payload.shares.quantize(Decimal("0.00000001"))
            transaction.price_per_share = payload.price_per_share.quantize(Decimal("0.00000001"))
            transaction.total_amount = payload.total_amount.quantize(Decimal("0.0001"))
            transaction.transaction_date = payload.transaction_date
            transaction.notes = payload.notes
            transaction.synced_at = synced_at
        upserted += 1
    session.flush()
    return upserted
