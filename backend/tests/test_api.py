from __future__ import annotations

import io
import os
import time
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from app.core.config import get_settings, refresh_settings_cache
from app.models import PriceHistory
from app.providers.brokerage_sync import MockBrokerageSyncProvider
from app.services import brokerage_sync as brokerage_sync_service


def test_account_and_holding_crud_flow(client):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Primary Brokerage",
            "account_type": "Individual Brokerage",
            "category": "brokerage",
            "brokerage": "Vanguard",
        },
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    holding_response = client.post(
        "/api/holdings",
        json={
            "account_id": account_id,
            "ticker": "AAPL",
            "name": "Apple",
            "shares": 10,
            "cost_basis": 1500,
            "purchase_date": "2024-01-15",
            "security_type": "equity",
            "market": "us",
            "currency": "USD",
        },
    )
    assert holding_response.status_code == 201
    assert holding_response.json()["ticker"] == "AAPL"

    portfolio_response = client.get("/api/portfolio?category=brokerage")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["holdings"]) == 1
    assert portfolio["summary"]["total_value"] != "0"

    delete_response = client.delete(f"/api/accounts/{account_id}")
    assert delete_response.status_code == 204
    assert client.get("/api/holdings").json() == []


def test_account_brokerage_aliases_are_normalized(client):
    create_response = client.post(
        "/api/accounts",
        json={
            "name": "Employer Plan",
            "account_type": "401k",
            "category": "retirement",
            "brokerage": "principal financial",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["brokerage"] == "Principal"

    update_response = client.put(
        f"/api/accounts/{payload['id']}",
        json={"brokerage": "slavic401k"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["brokerage"] == "Slavic 401k"


def test_csv_preview_and_commit(client):
    csv_bytes = io.BytesIO(
        b"ticker,shares,cost basis,purchase date,currency\nMSFT,5,1200,2024-02-01,USD\nINFY,20,31000,2024-03-01,INR\n"
    )
    preview_response = client.post(
        "/api/imports/preview",
        files={"file": ("portfolio.csv", csv_bytes, "text/csv")},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["row_count"] == 2

    commit_response = client.post(
        f"/api/imports/{preview['job_id']}/commit",
        json={
            "account": {
                "name": "Imported Brokerage",
                "account_type": "Joint Brokerage",
                "category": "brokerage",
                "brokerage": "Fidelity",
            },
            "replace_existing": False,
        },
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["imported_holdings"] == 2

    holdings_response = client.get("/api/holdings")
    assert holdings_response.status_code == 200
    assert {item["ticker"] for item in holdings_response.json()} == {"MSFT", "INFY"}


def test_excel_preview_and_commit(client):
    frame = pd.DataFrame(
        [
            {
                "Ticker": "AAPL",
                "Shares": 3,
                "Cost Basis": 540,
                "Purchase Date": "2024-01-15",
                "Currency": "USD",
            },
            {
                "Ticker": "HDFCBANK",
                "Shares": 12,
                "Cost Basis": 21000,
                "Purchase Date": "2024-02-20",
                "Currency": "INR",
            },
        ]
    )
    workbook = io.BytesIO()
    frame.to_excel(workbook, index=False)
    workbook.seek(0)

    preview_response = client.post(
        "/api/imports/preview",
        files={
            "file": (
                "portfolio.xlsx",
                workbook.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["row_count"] == 2
    assert preview["preview_rows"][1]["currency"] == "INR"

    commit_response = client.post(
        f"/api/imports/{preview['job_id']}/commit",
        json={
            "account": {
                "name": "Excel Import Account",
                "account_type": "Individual Brokerage",
                "category": "india",
                "brokerage": "charles schwab",
            },
            "replace_existing": False,
        },
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["imported_holdings"] == 2

    accounts_response = client.get("/api/accounts")
    assert accounts_response.status_code == 200
    assert any(account["brokerage"] == "Schwab" for account in accounts_response.json())


def test_refresh_job_lifecycle(client):
    response = client.post(
        "/api/jobs/refresh-prices",
        json={"tickers": [], "include_benchmarks": True},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    status_payload = response.json()
    for _ in range(20):
        if status_payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.2)
        status_payload = client.get(f"/api/jobs/{job_id}").json()

    assert status_payload["status"] == "completed"
    assert "refreshed_rows" in status_payload["result"]


def test_transaction_crud_and_investment_summary(client):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Contribution Account",
            "account_type": "Individual Brokerage",
            "category": "brokerage",
            "brokerage": "Vanguard",
        },
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    deposit_response = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "ticker": "CASH",
            "transaction_type": "deposit",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 2500,
            "transaction_date": "2026-01-05",
            "notes": "Initial contribution",
        },
    )
    assert deposit_response.status_code == 201

    buy_response = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "ticker": "AAPL",
            "transaction_type": "buy",
            "shares": 5,
            "price_per_share": 180,
            "transaction_date": "2026-01-10",
            "notes": "Bought shares",
        },
    )
    assert buy_response.status_code == 201
    transaction_id = buy_response.json()["id"]
    assert buy_response.json()["total_amount"] == "900.0000"

    summary_response = client.get("/api/investments/summary?category=brokerage&year=2026")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["transaction_count"] == 2
    assert summary["contributions"] == "3400.0000"
    assert summary["net_investment"] == "3400.0000"

    update_response = client.put(
        f"/api/transactions/{transaction_id}",
        json={"price_per_share": 185, "shares": 5},
    )
    assert update_response.status_code == 200
    assert update_response.json()["total_amount"] == "925.0000"

    list_response = client.get("/api/transactions?category=brokerage&year=2026")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    delete_response = client.delete(f"/api/transactions/{transaction_id}")
    assert delete_response.status_code == 204


def test_investment_summary_returns_breakdown_and_cumulative_months(client):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Analytics Account",
            "account_type": "Individual Brokerage",
            "category": "brokerage",
            "brokerage": "Fidelity",
        },
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    transactions = [
        {
            "account_id": account_id,
            "ticker": "CASH",
            "transaction_type": "deposit",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 2400,
            "transaction_date": "2026-01-03",
        },
        {
            "account_id": account_id,
            "ticker": "VTI",
            "transaction_type": "buy",
            "shares": 4,
            "price_per_share": 250,
            "transaction_date": "2026-02-10",
        },
        {
            "account_id": account_id,
            "ticker": "CASH",
            "transaction_type": "withdrawal",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 500,
            "transaction_date": "2026-03-11",
        },
        {
            "account_id": account_id,
            "ticker": "VTI",
            "transaction_type": "dividend",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 45,
            "transaction_date": "2026-03-28",
        },
    ]

    for payload in transactions:
        response = client.post("/api/transactions", json=payload)
        assert response.status_code == 201

    summary_response = client.get("/api/investments/summary?category=brokerage&year=2026")
    assert summary_response.status_code == 200
    summary = summary_response.json()

    assert summary["contributions"] == "3400.0000"
    assert summary["withdrawals"] == "500.0000"
    assert summary["dividends"] == "45.0000"
    assert summary["net_investment"] == "2900.0000"
    assert summary["average_monthly_net"] == "241.6667"
    assert summary["average_monthly_dividends"] == "3.7500"
    assert summary["active_months"] == 3
    assert summary["monthly"][0]["cumulative_net_investment"] == "2400.0000"
    assert summary["monthly"][1]["cumulative_net_investment"] == "3400.0000"
    assert summary["monthly"][2]["cumulative_net_investment"] == "2900.0000"
    assert summary["best_month"] == {"month": "Jan", "amount": "2400.0000"}
    assert summary["largest_outflow_month"] == {"month": "Mar", "amount": "-500.0000"}
    assert summary["type_breakdown"][0] == {
        "label": "Deposit",
        "amount": "2400.0000",
        "count": 1,
    }


def test_portfolio_analytics_returns_advanced_metrics_and_aggregates_dividend_positions(client, db_session):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Dividend Brokerage",
            "account_type": "Individual Brokerage",
            "category": "brokerage",
            "brokerage": "Vanguard",
        },
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    holdings = [
        {
            "account_id": account_id,
            "ticker": "AAPL",
            "name": "Apple",
            "shares": 4,
            "cost_basis": 600,
            "purchase_date": "2025-01-10",
            "security_type": "equity",
            "market": "us",
            "currency": "USD",
        },
        {
            "account_id": account_id,
            "ticker": "AAPL",
            "name": "Apple",
            "shares": 2,
            "cost_basis": 330,
            "purchase_date": "2025-03-15",
            "security_type": "equity",
            "market": "us",
            "currency": "USD",
        },
        {
            "account_id": account_id,
            "ticker": "VTI",
            "name": "Vanguard Total Stock Market ETF",
            "shares": 5,
            "cost_basis": 1200,
            "purchase_date": "2025-01-10",
            "security_type": "etf",
            "market": "us",
            "currency": "USD",
        },
    ]

    for payload in holdings:
        response = client.post("/api/holdings", json=payload)
        assert response.status_code == 201

    today = date.today()
    yesterday = today - timedelta(days=1)
    year_start = date(today.year, 1, 1)
    prior_year = today - timedelta(days=365)

    db_session.add_all(
        [
            PriceHistory(
                ticker="AAPL",
                price_date=prior_year,
                close_price=Decimal("150"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.008"),
            ),
            PriceHistory(
                ticker="AAPL",
                price_date=year_start,
                close_price=Decimal("170"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.008"),
            ),
            PriceHistory(
                ticker="AAPL",
                price_date=yesterday,
                close_price=Decimal("190"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.008"),
            ),
            PriceHistory(
                ticker="AAPL",
                price_date=today,
                close_price=Decimal("195"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.008"),
            ),
            PriceHistory(
                ticker="VTI",
                price_date=prior_year,
                close_price=Decimal("220"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.015"),
            ),
            PriceHistory(
                ticker="VTI",
                price_date=year_start,
                close_price=Decimal("240"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.015"),
            ),
            PriceHistory(
                ticker="VTI",
                price_date=yesterday,
                close_price=Decimal("265"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.015"),
            ),
            PriceHistory(
                ticker="VTI",
                price_date=today,
                close_price=Decimal("270"),
                currency="USD",
                source="test",
                dividend_yield=Decimal("0.015"),
            ),
            PriceHistory(
                ticker="SPY",
                price_date=prior_year,
                close_price=Decimal("500"),
                currency="USD",
                source="test",
            ),
            PriceHistory(
                ticker="SPY",
                price_date=year_start,
                close_price=Decimal("510"),
                currency="USD",
                source="test",
            ),
            PriceHistory(
                ticker="SPY",
                price_date=today,
                close_price=Decimal("530"),
                currency="USD",
                source="test",
            ),
            PriceHistory(
                ticker="QQQ",
                price_date=prior_year,
                close_price=Decimal("430"),
                currency="USD",
                source="test",
            ),
            PriceHistory(
                ticker="QQQ",
                price_date=year_start,
                close_price=Decimal("440"),
                currency="USD",
                source="test",
            ),
            PriceHistory(
                ticker="QQQ",
                price_date=today,
                close_price=Decimal("460"),
                currency="USD",
                source="test",
            ),
        ]
    )
    db_session.commit()

    for payload in [
        {
            "account_id": account_id,
            "ticker": "CASH",
            "transaction_type": "deposit",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 1000,
            "transaction_date": today.isoformat(),
        },
        {
            "account_id": account_id,
            "ticker": "CASH",
            "transaction_type": "withdrawal",
            "shares": 0,
            "price_per_share": 0,
            "total_amount": 200,
            "transaction_date": yesterday.isoformat(),
        },
    ]:
        response = client.post("/api/transactions", json=payload)
        assert response.status_code == 201

    analytics_response = client.get("/api/portfolio-analytics?category=brokerage")
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()

    assert analytics["time_weighted_return_ytd"] != "0"
    assert analytics["time_weighted_return_1y"] != "0"
    assert float(analytics["max_drawdown_1y"]) <= 0
    assert analytics["top_three_concentration_pct"] == "100.00"
    assert analytics["annual_dividend_income"] != "0.0000"
    assert analytics["portfolio_yield_pct"] != "0"
    assert analytics["benchmark_spread_1y"]
    assert {item["ticker"] for item in analytics["top_dividend_positions"]} >= {"AAPL", "VTI"}
    assert len([item for item in analytics["top_dividend_positions"] if item["ticker"] == "AAPL"]) == 1
    assert {item["label"] for item in analytics["index_exposure"]} >= {"NASDAQ 100", "US Total Market"}
    assert analytics["quantstats"]["period"] == "1y"
    assert analytics["quantstats"]["trading_days"] > 0
    assert analytics["quantstats"]["sharpe_ratio"] != "0.00"
    assert analytics["quantstats"]["cagr_pct"] != "0.00"
    assert analytics["quantstats"]["volatility_pct"] != "0.00"


def test_auth_login_unlocks_protected_endpoints(client):
    settings = get_settings()
    original_password = settings.auth_password
    settings.auth_password = "open-sesame"
    try:
        locked_response = client.get("/api/accounts")
        assert locked_response.status_code == 401

        session_response = client.get("/api/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["enabled"] is True
        assert session_response.json()["authenticated"] is False

        login_response = client.post("/api/auth/login", json={"password": "open-sesame"})
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        assert token

        unlocked_response = client.get("/api/accounts", headers={"Authorization": f"Bearer {token}"})
        assert unlocked_response.status_code == 200
    finally:
        settings.auth_password = original_password


def test_auth_allows_cors_preflight_for_protected_endpoints(client):
    settings = get_settings()
    original_password = settings.auth_password
    settings.auth_password = "open-sesame"
    try:
        response = client.options(
            "/api/accounts",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    finally:
        settings.auth_password = original_password


def test_observability_and_metrics_surface_runtime_data(client):
    health_response = client.get("/api/health")
    assert health_response.status_code == 200

    observability_response = client.get("/api/ops/observability")
    assert observability_response.status_code == 200
    observability = observability_response.json()
    assert observability["database_ok"] is True
    assert observability["total_requests"] >= 1
    assert any(item["path"] == "/api/health" for item in observability["endpoints"])

    metrics_response = client.get("/api/ops/metrics")
    assert metrics_response.status_code == 200
    assert "portfolio_requests_total" in metrics_response.text


def _enable_mock_brokerage_sync(monkeypatch):
    settings = SimpleNamespace(
        brokerage_sync_enabled=True,
        brokerage_sync_local_profile_id="test-household",
        brokerage_sync_activity_lookback_days=365,
    )
    monkeypatch.setattr(
        brokerage_sync_service,
        "_provider",
        lambda: (settings, MockBrokerageSyncProvider()),
    )


def test_brokerage_sync_status_connect_and_sync_flow(client, monkeypatch):
    _enable_mock_brokerage_sync(monkeypatch)

    status_response = client.get("/api/brokerage-sync/status")
    assert status_response.status_code == 200
    assert status_response.json()["synced_accounts"] == []

    connect_response = client.post("/api/brokerage-sync/connect")
    assert connect_response.status_code == 200
    connect_payload = connect_response.json()
    assert connect_payload["provider"] == "mock"
    assert connect_payload["portal_url"].startswith("https://example.test/")

    sync_response = client.post("/api/brokerage-sync/sync")
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["accounts_synced"] == 2
    assert sync_payload["holdings_synced"] == 3
    assert sync_payload["cash_transactions_synced"] == 3

    accounts_response = client.get("/api/accounts")
    assert accounts_response.status_code == 200
    synced_accounts = [account for account in accounts_response.json() if account.get("sync_provider") == "mock"]
    assert {account["name"] for account in synced_accounts} == {"Wealthfront Taxable", "Principal 401k"}
    assert all(account["sync_status"] == "synced" for account in synced_accounts)

    holdings_response = client.get("/api/holdings")
    assert holdings_response.status_code == 200
    assert {holding["ticker"] for holding in holdings_response.json()} == {"VTI", "VXUS", "VOO"}

    transactions_response = client.get("/api/transactions")
    assert transactions_response.status_code == 200
    assert len(transactions_response.json()) == 3

    second_sync_response = client.post("/api/brokerage-sync/sync")
    assert second_sync_response.status_code == 200
    assert second_sync_response.json()["cash_transactions_synced"] == 3

    transactions_after_second_sync = client.get("/api/transactions").json()
    assert len(transactions_after_second_sync) == 3

    status_after_sync = client.get("/api/brokerage-sync/status").json()
    assert status_after_sync["total_synced_holdings"] == 3
    assert status_after_sync["total_synced_transactions"] == 3


def test_brokerage_sync_config_can_be_saved_and_masks_consumer_key(client, monkeypatch, tmp_path):
    env_path = tmp_path / "local-settings.env"
    original_env = {
        "BROKERAGE_SYNC_PROVIDER": os.environ.get("BROKERAGE_SYNC_PROVIDER"),
        "SNAPTRADE_CLIENT_ID": os.environ.get("SNAPTRADE_CLIENT_ID"),
        "SNAPTRADE_CONSUMER_KEY": os.environ.get("SNAPTRADE_CONSUMER_KEY"),
        "SNAPTRADE_REDIRECT_URI": os.environ.get("SNAPTRADE_REDIRECT_URI"),
    }
    monkeypatch.setenv("PORTFOLIO_SETTINGS_FILE", str(env_path))
    refresh_settings_cache(
        {
            "BROKERAGE_SYNC_PROVIDER": None,
            "SNAPTRADE_CLIENT_ID": None,
            "SNAPTRADE_CONSUMER_KEY": None,
            "SNAPTRADE_REDIRECT_URI": None,
        }
    )

    try:
        read_response = client.get("/api/settings/brokerage-sync-config")
        assert read_response.status_code == 200
        assert read_response.json()["provider"] == "disabled"
        assert read_response.json()["consumer_key_configured"] is False

        save_response = client.put(
            "/api/settings/brokerage-sync-config",
            json={
                "provider": "snaptrade",
                "snaptrade_client_id": "client-123",
                "snaptrade_consumer_key": "secret-value-1234",
                "snaptrade_redirect_uri": "http://127.0.0.1:5173/settings",
            },
        )
        assert save_response.status_code == 200
        payload = save_response.json()
        assert payload["provider"] == "snaptrade"
        assert payload["snaptrade_client_id"] == "client-123"
        assert payload["snaptrade_redirect_uri"] == "http://127.0.0.1:5173/settings"
        assert payload["consumer_key_configured"] is True
        assert payload["consumer_key_masked"].endswith("1234")
        assert "secret-value-1234" not in str(payload)

        saved_env = env_path.read_text(encoding="utf-8")
        assert "BROKERAGE_SYNC_PROVIDER=snaptrade" in saved_env
        assert "SNAPTRADE_CLIENT_ID=client-123" in saved_env
        assert "SNAPTRADE_CONSUMER_KEY=secret-value-1234" in saved_env
        assert "SNAPTRADE_REDIRECT_URI=http://127.0.0.1:5173/settings" in saved_env

        second_read = client.get("/api/settings/brokerage-sync-config")
        assert second_read.status_code == 200
        assert second_read.json()["consumer_key_configured"] is True
        assert second_read.json()["consumer_key_masked"].endswith("1234")
    finally:
        refresh_settings_cache(original_env)
