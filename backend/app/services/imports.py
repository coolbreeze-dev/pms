from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.brokerages import normalize_brokerage
from app.imports.csv_adapters import ADAPTERS, ParsedImportRow
from app.models import Account, Holding, ImportJob, ImportRow
from app.schemas.api import (
    ImportAccountSuggestion,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportJobRead,
    ImportPreviewResponse,
    ImportReconciliationSummary,
    NormalizedImportRow,
)


def _normalize_row(parsed: ParsedImportRow) -> dict:
    return {
        "row_index": parsed.row_index,
        "ticker": parsed.ticker,
        "name": parsed.name,
        "shares": str(parsed.shares),
        "cost_basis": str(parsed.cost_basis),
        "purchase_date": parsed.purchase_date.isoformat(),
        "security_type": parsed.security_type,
        "market": parsed.market,
        "currency": parsed.currency,
        "account_name": parsed.account_name,
        "brokerage": normalize_brokerage(parsed.brokerage) if parsed.brokerage else None,
        "cost_basis_source": parsed.cost_basis_source,
        "ticker_inferred": parsed.ticker_inferred,
        "reconciliation_status": "new",
        "matched_account_id": None,
        "matched_account_name": None,
        "matched_account_brokerage": None,
        "matched_existing_holdings": 0,
        "duplicate_row_count": 1,
        "review_notes": list(parsed.review_notes),
    }


def _normalize_match_key(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _lot_key(
    ticker: str,
    shares: Decimal,
    cost_basis: Decimal,
    purchase_date_value: date,
) -> tuple[str, str, str, str]:
    return (
        ticker.upper(),
        str(shares.quantize(Decimal("0.00000001"))),
        str(cost_basis.quantize(Decimal("0.0001"))),
        purchase_date_value.isoformat(),
    )


def _build_reconciliation(
    session: Session, normalized_rows: list[dict]
) -> tuple[list[dict], ImportReconciliationSummary]:
    accounts = session.scalars(select(Account).order_by(Account.brokerage.asc(), Account.name.asc())).all()
    holdings = session.scalars(select(Holding)).all()

    accounts_by_exact_key: dict[tuple[str, str], list[Account]] = defaultdict(list)
    accounts_by_name: dict[str, list[Account]] = defaultdict(list)
    accounts_by_brokerage: dict[str, list[Account]] = defaultdict(list)
    lot_keys_by_account: dict[int, set[tuple[str, str, str, str]]] = defaultdict(set)
    ticker_counts_by_account: dict[int, dict[str, int]] = defaultdict(dict)

    for account in accounts:
        normalized_name = _normalize_match_key(account.name)
        normalized_brokerage = _normalize_match_key(normalize_brokerage(account.brokerage))
        accounts_by_exact_key[(normalized_name, normalized_brokerage)].append(account)
        accounts_by_name[normalized_name].append(account)
        accounts_by_brokerage[normalized_brokerage].append(account)

    for holding in holdings:
        lot_keys_by_account[holding.account_id].add(
            _lot_key(holding.ticker, holding.shares, holding.cost_basis, holding.purchase_date)
        )
        ticker_counts_by_account[holding.account_id][holding.ticker.upper()] = (
            ticker_counts_by_account[holding.account_id].get(holding.ticker.upper(), 0) + 1
        )

    duplicate_counts: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
    for row in normalized_rows:
        duplicate_counts[
            (
                row["ticker"],
                row["purchase_date"],
                row["shares"],
                row["cost_basis"],
                _normalize_match_key(row.get("account_name")),
                _normalize_match_key(row.get("brokerage")),
            )
        ] += 1

    suggestion_counts: dict[int, dict[str, int | str]] = {}
    annotated_rows: list[dict] = []

    for row in normalized_rows:
        reviewed = dict(row)
        notes = list(reviewed.get("review_notes", []))
        normalized_name = _normalize_match_key(reviewed.get("account_name"))
        normalized_brokerage = _normalize_match_key(reviewed.get("brokerage"))
        matched_account: Account | None = None
        reason = ""

        exact_matches = (
            accounts_by_exact_key.get((normalized_name, normalized_brokerage), [])
            if normalized_name and normalized_brokerage
            else []
        )
        if len(exact_matches) == 1:
            matched_account = exact_matches[0]
            reason = "Matched the source account name and brokerage."
        elif normalized_name:
            name_matches = accounts_by_name.get(normalized_name, [])
            if len(name_matches) == 1:
                matched_account = name_matches[0]
                reason = "Matched the source account name."
            elif len(name_matches) > 1:
                notes.append("Multiple existing accounts share this account name. Pick the target account manually.")
        elif normalized_brokerage:
            brokerage_matches = accounts_by_brokerage.get(normalized_brokerage, [])
            if len(brokerage_matches) == 1:
                matched_account = brokerage_matches[0]
                reason = "Matched the only existing account at this brokerage."
            elif len(brokerage_matches) > 1:
                notes.append("Multiple existing accounts use this brokerage. Pick the target account manually.")

        if matched_account:
            reviewed["matched_account_id"] = matched_account.id
            reviewed["matched_account_name"] = matched_account.name
            reviewed["matched_account_brokerage"] = matched_account.brokerage
            if matched_account.id not in suggestion_counts:
                suggestion_counts[matched_account.id] = {
                    "matched_rows": 0,
                    "matched_existing_holdings": 0,
                    "reason": reason,
                }
            suggestion_counts[matched_account.id]["matched_rows"] = int(
                suggestion_counts[matched_account.id]["matched_rows"]
            ) + 1

        matching_existing_holdings = 0
        if matched_account:
            matching_existing_holdings = ticker_counts_by_account.get(matched_account.id, {}).get(
                reviewed["ticker"], 0
            )
            reviewed["matched_existing_holdings"] = matching_existing_holdings
            if matching_existing_holdings:
                notes.append(
                    f"{matching_existing_holdings} existing holding(s) already use this ticker in the matched account."
                )
                suggestion_counts[matched_account.id]["matched_existing_holdings"] = int(
                    suggestion_counts[matched_account.id]["matched_existing_holdings"]
                ) + matching_existing_holdings

        duplicate_key = (
            reviewed["ticker"],
            reviewed["purchase_date"],
            reviewed["shares"],
            reviewed["cost_basis"],
            normalized_name,
            normalized_brokerage,
        )
        reviewed["duplicate_row_count"] = duplicate_counts[duplicate_key]
        if reviewed["duplicate_row_count"] > 1:
            notes.append(
                f"This same lot appears {reviewed['duplicate_row_count']} times in the uploaded file."
            )

        if reviewed["cost_basis_source"] != "reported":
            notes.append(
                "Verify the imported cost basis before commit because it was inferred from the export."
            )

        if reviewed["ticker_inferred"]:
            notes.append("Review the inferred ticker before commit if you want a different symbol label.")

        reviewed["review_notes"] = notes
        if notes:
            reviewed["reconciliation_status"] = "review"
        elif matched_account:
            reviewed["reconciliation_status"] = "matched"
        else:
            reviewed["reconciliation_status"] = "new"

        annotated_rows.append(reviewed)

    account_suggestions: list[ImportAccountSuggestion] = []
    for account in accounts:
        summary = suggestion_counts.get(account.id)
        if not summary:
            continue
        account_suggestions.append(
            ImportAccountSuggestion(
                account_id=account.id,
                account_name=account.name,
                brokerage=account.brokerage,
                matched_rows=int(summary["matched_rows"]),
                matched_existing_holdings=int(summary["matched_existing_holdings"]),
                reason=str(summary["reason"]),
            )
        )
    account_suggestions.sort(key=lambda item: (-item.matched_rows, item.brokerage, item.account_name))

    suggested_account = None
    if account_suggestions:
        suggested_account = account_suggestions[0]
        if len(account_suggestions) > 1 and account_suggestions[0].matched_rows == account_suggestions[1].matched_rows:
            suggested_account = None

    return annotated_rows, ImportReconciliationSummary(
        suggested_account_id=suggested_account.account_id if suggested_account else None,
        suggested_account_name=suggested_account.account_name if suggested_account else None,
        suggested_brokerage=suggested_account.brokerage if suggested_account else None,
        duplicate_rows_in_file=sum(1 for row in annotated_rows if row["duplicate_row_count"] > 1),
        rows_matching_existing_holdings=sum(
            1 for row in annotated_rows if row["matched_existing_holdings"] > 0
        ),
        rows_with_account_match=sum(1 for row in annotated_rows if row["matched_account_id"] is not None),
        rows_needing_review=sum(1 for row in annotated_rows if row["reconciliation_status"] == "review"),
        detected_brokerages=sorted(
            {row["brokerage"] for row in annotated_rows if row.get("brokerage")}
        ),
        account_suggestions=account_suggestions,
    )


def _reconciliation_from_job_rows(rows: list[ImportRow]) -> ImportReconciliationSummary:
    normalized_rows = [dict(row.normalized_payload) for row in rows]
    account_rollup: dict[int, dict[str, int | str]] = {}
    detected_brokerages = sorted({row["brokerage"] for row in normalized_rows if row.get("brokerage")})
    for row in normalized_rows:
        account_id = row.get("matched_account_id")
        if account_id is None:
            continue
        if account_id not in account_rollup:
            account_rollup[account_id] = {
                "account_name": row.get("matched_account_name") or "Account",
                "brokerage": row.get("matched_account_brokerage") or "",
                "matched_rows": 0,
                "matched_existing_holdings": 0,
                "reason": "Matched from import preview.",
            }
        account_rollup[account_id]["matched_rows"] = int(account_rollup[account_id]["matched_rows"]) + 1
        account_rollup[account_id]["matched_existing_holdings"] = int(
            account_rollup[account_id]["matched_existing_holdings"]
        ) + int(row.get("matched_existing_holdings") or 0)
    account_suggestions = [
        ImportAccountSuggestion(
            account_id=account_id,
            account_name=str(summary["account_name"]),
            brokerage=str(summary["brokerage"]),
            matched_rows=int(summary["matched_rows"]),
            matched_existing_holdings=int(summary["matched_existing_holdings"]),
            reason=str(summary["reason"]),
        )
        for account_id, summary in account_rollup.items()
    ]
    account_suggestions.sort(key=lambda item: (-item.matched_rows, item.brokerage, item.account_name))
    suggested = account_suggestions[0] if len(account_suggestions) == 1 else None
    if len(account_suggestions) > 1 and account_suggestions[0].matched_rows > account_suggestions[1].matched_rows:
        suggested = account_suggestions[0]
    return ImportReconciliationSummary(
        suggested_account_id=suggested.account_id if suggested else None,
        suggested_account_name=suggested.account_name if suggested else None,
        suggested_brokerage=suggested.brokerage if suggested else None,
        duplicate_rows_in_file=sum(1 for row in normalized_rows if int(row.get("duplicate_row_count", 1)) > 1),
        rows_matching_existing_holdings=sum(
            1 for row in normalized_rows if int(row.get("matched_existing_holdings", 0)) > 0
        ),
        rows_with_account_match=sum(1 for row in normalized_rows if row.get("matched_account_id") is not None),
        rows_needing_review=sum(1 for row in normalized_rows if row.get("reconciliation_status") == "review"),
        detected_brokerages=detected_brokerages,
        account_suggestions=account_suggestions,
    )


def preview_import(session: Session, filename: str, content_type: str | None, payload: bytes) -> ImportPreviewResponse:
    if filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF parsing is deferred. Use CSV or Excel (.xlsx/.xls) for the current MVP.",
        )

    detected_adapter = None
    parsed_rows: list[ParsedImportRow] = []
    warnings: list[str] = []
    for adapter in ADAPTERS:
        try:
            parsed_rows, warnings = adapter.parse(filename, payload)
            detected_adapter = adapter
            break
        except ValueError:
            continue

    if detected_adapter is None:
        raise HTTPException(status_code=400, detail="No CSV import adapter matched the uploaded file.")

    import_job = ImportJob(
        filename=filename,
        content_type=content_type,
        adapter_name=detected_adapter.name,
        status="previewed",
        warnings=warnings,
    )
    session.add(import_job)
    session.flush()

    normalized_rows = [_normalize_row(parsed_row) for parsed_row in parsed_rows]
    reconciled_rows, reconciliation = _build_reconciliation(session, normalized_rows)

    preview_rows: list[NormalizedImportRow] = []
    for normalized in reconciled_rows:
        session.add(
            ImportRow(
                import_job_id=import_job.id,
                row_index=normalized["row_index"],
                raw_payload=normalized,
                normalized_payload=normalized,
                status="previewed",
            )
        )
        preview_rows.append(NormalizedImportRow(**normalized))
    session.commit()
    return ImportPreviewResponse(
        job_id=import_job.id,
        adapter_name=import_job.adapter_name,
        status=import_job.status,
        row_count=len(preview_rows),
        warnings=warnings,
        reconciliation=reconciliation,
        preview_rows=preview_rows,
    )


def get_import_job(session: Session, job_id: int) -> ImportJobRead:
    job = session.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")
    preview_rows = [NormalizedImportRow(**row.normalized_payload) for row in job.rows]
    return ImportJobRead(
        id=job.id,
        filename=job.filename,
        adapter_name=job.adapter_name,
        status=job.status,
        warnings=job.warnings,
        created_at=job.created_at,
        committed_at=job.committed_at,
        reconciliation=_reconciliation_from_job_rows(job.rows),
        preview_rows=preview_rows,
    )


def commit_import(session: Session, job_id: int, request: ImportCommitRequest) -> ImportCommitResponse:
    job = session.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")
    if job.status == "committed":
        return ImportCommitResponse(
            job_id=job.id,
            status=job.status,
            imported_holdings=0,
            skipped_duplicate_holdings=0,
        )

    account = None
    created_account_id = None
    if request.account_id is not None:
        account = session.get(Account, request.account_id)
    elif request.account is not None:
        account = Account(
            name=request.account.name,
            account_type=request.account.account_type,
            category=request.account.category,
            brokerage=normalize_brokerage(request.account.brokerage),
        )
        session.add(account)
        session.flush()
        created_account_id = account.id

    if account is None:
        raise HTTPException(status_code=400, detail="An existing or new account is required to commit.")

    if request.replace_existing:
        existing_holdings = session.scalars(select(Holding).where(Holding.account_id == account.id)).all()
        for holding in existing_holdings:
            session.delete(holding)
        session.flush()

    imported_count = 0
    skipped_duplicate_count = 0
    existing_lot_keys = {
        _lot_key(holding.ticker, holding.shares, holding.cost_basis, holding.purchase_date)
        for holding in session.scalars(select(Holding).where(Holding.account_id == account.id)).all()
    }
    for row in job.rows:
        normalized = row.normalized_payload
        shares = Decimal(normalized["shares"])
        cost_basis = Decimal(normalized["cost_basis"])
        purchase_date_value = date.fromisoformat(normalized["purchase_date"])
        lot_key = _lot_key(normalized["ticker"], shares, cost_basis, purchase_date_value)
        if request.skip_existing_matching_holdings and lot_key in existing_lot_keys:
            skipped_duplicate_count += 1
            row.status = "skipped"
            row.error_message = "Skipped exact duplicate lot during import reconciliation."
            continue
        cost_basis_per_share = (
            (cost_basis / shares).quantize(Decimal("0.00000001")) if shares else Decimal("0")
        )
        session.add(
            Holding(
                account_id=account.id,
                ticker=normalized["ticker"],
                name=normalized.get("name"),
                shares=shares,
                cost_basis=cost_basis,
                cost_basis_per_share=cost_basis_per_share,
                purchase_date=purchase_date_value,
                security_type=normalized["security_type"],
                market=normalized["market"],
                currency=normalized["currency"],
                import_source=job.adapter_name,
                import_job_id=job.id,
            )
        )
        row.status = "committed"
        imported_count += 1
        existing_lot_keys.add(lot_key)

    job.status = "committed"
    job.committed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()

    return ImportCommitResponse(
        job_id=job.id,
        status=job.status,
        imported_holdings=imported_count,
        skipped_duplicate_holdings=skipped_duplicate_count,
        created_account_id=created_account_id,
    )
