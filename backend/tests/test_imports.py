from __future__ import annotations

import io

import pandas as pd


def test_vanguard_preview_reconciles_to_existing_account(client):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Vanguard Taxable",
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
            "ticker": "MSFT",
            "name": "Microsoft",
            "shares": 5,
            "cost_basis": 1200,
            "purchase_date": "2024-02-01",
            "security_type": "equity",
            "market": "us",
            "currency": "USD",
        },
    )
    assert holding_response.status_code == 201

    csv_bytes = io.BytesIO(
        (
            "Vanguard household portfolio export\n"
            "Account Name,CUSIP/Symbol,Investment Name,Shares,Total Cost,Acquired Date\n"
            "Vanguard Taxable,MSFT,Microsoft Corp,5,1200,2024-02-01\n"
        ).encode("utf-8")
    )
    preview_response = client.post(
        "/api/imports/preview",
        files={"file": ("vanguard_positions.csv", csv_bytes, "text/csv")},
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["adapter_name"] == "vanguard_positions"
    assert preview["reconciliation"]["suggested_account_id"] == account_id
    assert preview["reconciliation"]["rows_matching_existing_holdings"] == 1
    row = preview["preview_rows"][0]
    assert row["brokerage"] == "Vanguard"
    assert row["matched_account_name"] == "Vanguard Taxable"
    assert row["matched_existing_holdings"] == 1
    assert row["reconciliation_status"] == "review"


def test_retirement_excel_import_infers_ticker_and_cost_basis(client):
    workbook = io.BytesIO()
    pd.DataFrame(
        [
            {
                "Account Name": "Employer 401k",
                "Investment Option": "Vanguard 500 Index Fund",
                "Units": 12.5,
                "Balance": 4200.25,
            }
        ]
    ).to_excel(workbook, index=False)
    workbook.seek(0)

    preview_response = client.post(
        "/api/imports/preview",
        files={
            "file": (
                "empower_plan.xlsx",
                workbook.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["adapter_name"] == "empower_retirement"
    row = preview["preview_rows"][0]
    assert row["ticker"].startswith("FUND:")
    assert row["ticker_inferred"] is True
    assert row["cost_basis_source"] == "market_value_fallback"
    assert any("cost basis" in note.lower() for note in row["review_notes"])


def test_commit_import_skips_exact_duplicate_lots_by_default(client):
    account_response = client.post(
        "/api/accounts",
        json={
            "name": "Fidelity Brokerage",
            "account_type": "Individual Brokerage",
            "category": "brokerage",
            "brokerage": "Fidelity",
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

    csv_bytes = io.BytesIO(
        b"account name,brokerage,ticker,shares,cost basis,purchase date,currency\nFidelity Brokerage,Fidelity,AAPL,10,1500,2024-01-15,USD\n"
    )
    preview_response = client.post(
        "/api/imports/preview",
        files={"file": ("portfolio.csv", csv_bytes, "text/csv")},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()

    commit_response = client.post(
        f"/api/imports/{preview['job_id']}/commit",
        json={"account_id": account_id},
    )
    assert commit_response.status_code == 200
    payload = commit_response.json()
    assert payload["imported_holdings"] == 0
    assert payload["skipped_duplicate_holdings"] == 1

    holdings_response = client.get("/api/holdings")
    assert holdings_response.status_code == 200
    assert len(holdings_response.json()) == 1
