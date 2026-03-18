from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import issue_token, parse_bearer_token, verify_password, verify_token
from app.core.brokerages import normalize_brokerage
from app.core.config import get_settings
from app.db.session import get_session
from app.db.session import ping_database
from app.models import Account, BackgroundJob, Holding
from app.schemas.api import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    AnalyticsResponse,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthSessionRead,
    BackgroundJobRead,
    BrokerageSyncConnectResponse,
    BrokerageSyncConfigRead,
    BrokerageSyncConfigUpdate,
    BrokerageSyncRunResponse,
    BrokerageSyncStatusResponse,
    CategoryPerformanceResponse,
    HoldingCreate,
    HoldingRead,
    HoldingUpdate,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportJobRead,
    ImportPreviewResponse,
    JobRequest,
    InvestmentSummaryResponse,
    ObservabilityResponse,
    PerformanceResponse,
    PortfolioResponse,
    SnapshotRead,
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
)
from app.services.brokerage_sync import (
    create_brokerage_connect_portal,
    get_brokerage_sync_status,
    run_brokerage_sync,
)
from app.services.imports import commit_import, get_import_job, preview_import
from app.services.jobs import enqueue_refresh_job
from app.services.jobs import scheduler
from app.services.portfolio import (
    get_analytics,
    get_category_performance,
    get_last_updated,
    get_performance,
    get_portfolio,
    list_holdings,
    list_snapshots,
)
from app.services.runtime_settings import get_brokerage_sync_config, update_brokerage_sync_config
from app.services.transactions import (
    create_transaction,
    delete_transaction,
    get_investment_summary,
    list_transactions,
    update_transaction,
)

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
def readiness() -> dict[str, str]:
    ping_database()
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}


@router.get("/auth/session", response_model=AuthSessionRead)
def auth_session(request: Request) -> AuthSessionRead:
    settings = get_settings()
    expires_at = verify_token(parse_bearer_token(request.headers.get("Authorization")), settings)
    return AuthSessionRead(
        enabled=settings.auth_enabled,
        authenticated=not settings.auth_enabled or expires_at is not None,
        expires_at=expires_at,
    )


@router.post("/auth/login", response_model=AuthLoginResponse)
def auth_login(payload: AuthLoginRequest) -> AuthLoginResponse:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthLoginResponse(enabled=False, authenticated=True, token=None, expires_at=None)
    if not verify_password(payload.password, settings):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token, expires_at = issue_token(settings)
    return AuthLoginResponse(enabled=True, authenticated=True, token=token, expires_at=expires_at)


@router.get("/accounts", response_model=list[AccountRead])
def get_accounts(session: Session = Depends(get_session)) -> list[Account]:
    return session.query(Account).order_by(Account.name).all()


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, session: Session = Depends(get_session)) -> Account:
    account = Account(**{**payload.model_dump(), "brokerage": normalize_brokerage(payload.brokerage)})
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.put("/accounts/{account_id}", response_model=AccountRead)
def update_account(account_id: int, payload: AccountUpdate, session: Session = Depends(get_session)) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "brokerage":
            value = normalize_brokerage(value)
        setattr(account, field, value)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, session: Session = Depends(get_session)) -> None:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    session.delete(account)
    session.commit()


@router.get("/holdings", response_model=list[HoldingRead])
def get_holdings(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[HoldingRead]:
    return list_holdings(session, category=category, search=search)


@router.post("/holdings", response_model=HoldingRead, status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingCreate, session: Session = Depends(get_session)) -> HoldingRead:
    account = session.get(Account, payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    cost_basis_per_share = (
        (payload.cost_basis / payload.shares).quantize(Decimal("0.00000001"))
        if payload.shares
        else Decimal("0")
    )
    holding = Holding(
        **payload.model_dump(exclude={"cost_basis"}),
        cost_basis=payload.cost_basis,
        cost_basis_per_share=cost_basis_per_share,
    )
    session.add(holding)
    session.commit()
    refreshed = list_holdings(session, search=holding.ticker)
    return next(item for item in refreshed if item.id == holding.id)


@router.put("/holdings/{holding_id}", response_model=HoldingRead)
def update_holding(holding_id: int, payload: HoldingUpdate, session: Session = Depends(get_session)) -> HoldingRead:
    holding = session.get(Holding, holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found.")
    data = payload.model_dump(exclude_none=True)
    for field, value in data.items():
        setattr(holding, field, value)
    if holding.shares:
        holding.cost_basis_per_share = (holding.cost_basis / holding.shares).quantize(Decimal("0.00000001"))
    session.commit()
    refreshed = list_holdings(session, search=holding.ticker)
    return next(item for item in refreshed if item.id == holding_id)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, session: Session = Depends(get_session)) -> None:
    holding = session.get(Holding, holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found.")
    session.delete(holding)
    session.commit()


@router.get("/portfolio", response_model=PortfolioResponse)
def portfolio(category: str = Query(default="all"), session: Session = Depends(get_session)) -> PortfolioResponse:
    return get_portfolio(session, category=category)


@router.get("/performance", response_model=PerformanceResponse)
def performance(
    period: str = Query(default="6m"),
    category: str = Query(default="all"),
    session: Session = Depends(get_session),
) -> PerformanceResponse:
    return get_performance(session, category=category, period=period)


@router.get("/category-performance", response_model=CategoryPerformanceResponse)
def category_performance(
    period: str = Query(default="6m"),
    session: Session = Depends(get_session),
) -> CategoryPerformanceResponse:
    return get_category_performance(session, period=period)


@router.get("/portfolio-history", response_model=list[SnapshotRead])
def portfolio_history(session: Session = Depends(get_session)) -> list[SnapshotRead]:
    return list_snapshots(session)


@router.get("/portfolio-analytics")
def portfolio_analytics(
    category: str = Query(default="all"), session: Session = Depends(get_session)
) -> AnalyticsResponse:
    return get_analytics(session, category=category)


@router.get("/last-updated")
def last_updated(session: Session = Depends(get_session)) -> dict[str, str | None]:
    latest = get_last_updated(session)
    return {"last_updated": latest.isoformat() if latest else None}


@router.get("/ops/observability", response_model=ObservabilityResponse)
def observability(request: Request, session: Session = Depends(get_session)) -> ObservabilityResponse:
    settings = get_settings()
    try:
        ping_database()
        database_ok = True
    except Exception:
        database_ok = False
    latest = get_last_updated(session)
    return request.app.state.observability.snapshot(
        environment=settings.environment,
        auth_enabled=settings.auth_enabled,
        scheduler_running=scheduler.running,
        database_ok=database_ok,
        last_price_refresh=latest,
        max_endpoints=settings.observability_max_endpoints,
    )


@router.get("/brokerage-sync/status", response_model=BrokerageSyncStatusResponse)
def brokerage_sync_status(session: Session = Depends(get_session)) -> BrokerageSyncStatusResponse:
    return get_brokerage_sync_status(session)


@router.get("/settings/brokerage-sync-config", response_model=BrokerageSyncConfigRead)
def brokerage_sync_config() -> BrokerageSyncConfigRead:
    return get_brokerage_sync_config()


@router.put("/settings/brokerage-sync-config", response_model=BrokerageSyncConfigRead)
def save_brokerage_sync_config(payload: BrokerageSyncConfigUpdate) -> BrokerageSyncConfigRead:
    return update_brokerage_sync_config(payload)


@router.post("/brokerage-sync/connect", response_model=BrokerageSyncConnectResponse)
def brokerage_sync_connect(session: Session = Depends(get_session)) -> BrokerageSyncConnectResponse:
    return create_brokerage_connect_portal(session)


@router.post("/brokerage-sync/sync", response_model=BrokerageSyncRunResponse)
def brokerage_sync_sync(session: Session = Depends(get_session)) -> BrokerageSyncRunResponse:
    return run_brokerage_sync(session)


@router.get("/ops/metrics", response_class=PlainTextResponse)
def metrics(request: Request) -> PlainTextResponse:
    settings = get_settings()
    try:
        ping_database()
        database_ok = True
    except Exception:
        database_ok = False
    payload = request.app.state.observability.render_metrics(
        environment=settings.environment,
        auth_enabled=settings.auth_enabled,
        scheduler_running=scheduler.running,
        database_ok=database_ok,
    )
    return PlainTextResponse(payload)


@router.get("/transactions", response_model=list[TransactionRead])
def get_transactions(
    category: str | None = Query(default=None),
    year: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[TransactionRead]:
    return list_transactions(session, category=category, year=year)


@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction_route(
    payload: TransactionCreate, session: Session = Depends(get_session)
) -> TransactionRead:
    return create_transaction(session, payload)


@router.put("/transactions/{transaction_id}", response_model=TransactionRead)
def update_transaction_route(
    transaction_id: int, payload: TransactionUpdate, session: Session = Depends(get_session)
) -> TransactionRead:
    return update_transaction(session, transaction_id, payload)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction_route(transaction_id: int, session: Session = Depends(get_session)) -> None:
    delete_transaction(session, transaction_id)


@router.get("/investments/summary", response_model=InvestmentSummaryResponse)
def investment_summary(
    category: str = Query(default="all"),
    year: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> InvestmentSummaryResponse:
    return get_investment_summary(session, category=category, year=year)


@router.post("/imports/preview", response_model=ImportPreviewResponse)
async def preview_import_job(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ImportPreviewResponse:
    payload = await file.read()
    return preview_import(session, file.filename or "upload.csv", file.content_type, payload)


@router.get("/imports/{job_id}", response_model=ImportJobRead)
def import_job(job_id: int, session: Session = Depends(get_session)) -> ImportJobRead:
    return get_import_job(session, job_id)


@router.post("/imports/{job_id}/commit", response_model=ImportCommitResponse)
def import_commit(
    job_id: int, payload: ImportCommitRequest, session: Session = Depends(get_session)
) -> ImportCommitResponse:
    return commit_import(session, job_id, payload)


@router.post("/jobs/refresh-prices", response_model=BackgroundJobRead, status_code=status.HTTP_202_ACCEPTED)
def refresh_prices(
    payload: JobRequest, session: Session = Depends(get_session)
) -> BackgroundJob:
    session_factory = sessionmaker(
        bind=session.get_bind(), autoflush=False, autocommit=False, future=True
    )
    return enqueue_refresh_job(session, session_factory, payload)


@router.get("/jobs/{job_id}", response_model=BackgroundJobRead)
def get_job(job_id: str, session: Session = Depends(get_session)) -> BackgroundJob:
    job = session.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
