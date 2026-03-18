from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock

from app.schemas.api import EndpointMetric, ObservabilityResponse


@dataclass
class _EndpointAggregate:
    count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0


class ObservabilityStore:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self._lock = Lock()
        self._total_requests = 0
        self._total_errors = 0
        self._endpoints: dict[str, _EndpointAggregate] = defaultdict(_EndpointAggregate)

    def record(self, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._total_requests += 1
            if status_code >= 400:
                self._total_errors += 1
            aggregate = self._endpoints[path]
            aggregate.count += 1
            if status_code >= 400:
                aggregate.error_count += 1
            aggregate.total_duration_ms += duration_ms
            aggregate.max_duration_ms = max(aggregate.max_duration_ms, duration_ms)

    def snapshot(
        self,
        *,
        environment: str,
        auth_enabled: bool,
        scheduler_running: bool,
        database_ok: bool,
        last_price_refresh,
        max_endpoints: int,
    ) -> ObservabilityResponse:
        with self._lock:
            endpoints = [
                EndpointMetric(
                    path=path,
                    count=aggregate.count,
                    error_count=aggregate.error_count,
                    avg_duration_ms=Decimal(str(aggregate.total_duration_ms / aggregate.count)).quantize(
                        Decimal("0.01")
                    ),
                    max_duration_ms=Decimal(str(aggregate.max_duration_ms)).quantize(Decimal("0.01")),
                )
                for path, aggregate in sorted(
                    self._endpoints.items(),
                    key=lambda item: item[1].count,
                    reverse=True,
                )[:max_endpoints]
            ]
            uptime_seconds = max(int((datetime.now(timezone.utc) - self.started_at).total_seconds()), 0)
            error_rate_pct = (
                (Decimal(str(self._total_errors)) / Decimal(str(self._total_requests)) * Decimal("100")).quantize(
                    Decimal("0.01")
                )
                if self._total_requests
                else Decimal("0")
            )
            return ObservabilityResponse(
                environment=environment,
                auth_enabled=auth_enabled,
                scheduler_running=scheduler_running,
                database_ok=database_ok,
                last_price_refresh=last_price_refresh,
                uptime_seconds=uptime_seconds,
                total_requests=self._total_requests,
                total_errors=self._total_errors,
                error_rate_pct=error_rate_pct,
                endpoints=endpoints,
            )

    def render_metrics(
        self,
        *,
        environment: str,
        auth_enabled: bool,
        scheduler_running: bool,
        database_ok: bool,
    ) -> str:
        with self._lock:
            lines = [
                "# HELP portfolio_requests_total Total HTTP requests served.",
                "# TYPE portfolio_requests_total counter",
                f"portfolio_requests_total {self._total_requests}",
                "# HELP portfolio_errors_total Total HTTP requests served with status >= 400.",
                "# TYPE portfolio_errors_total counter",
                f"portfolio_errors_total {self._total_errors}",
                "# HELP portfolio_auth_enabled Whether password auth is enabled.",
                "# TYPE portfolio_auth_enabled gauge",
                f"portfolio_auth_enabled {1 if auth_enabled else 0}",
                "# HELP portfolio_scheduler_running Whether the background scheduler is running.",
                "# TYPE portfolio_scheduler_running gauge",
                f"portfolio_scheduler_running {1 if scheduler_running else 0}",
                "# HELP portfolio_database_ok Whether the database probe succeeded.",
                "# TYPE portfolio_database_ok gauge",
                f"portfolio_database_ok {1 if database_ok else 0}",
                "# HELP portfolio_environment_info Deployment environment label.",
                "# TYPE portfolio_environment_info gauge",
                f'portfolio_environment_info{{environment="{environment}"}} 1',
            ]
            for path, aggregate in sorted(self._endpoints.items(), key=lambda item: item[0]):
                safe_path = path.replace("\\", "\\\\").replace('"', '\\"')
                lines.extend(
                    [
                        f'portfolio_endpoint_requests_total{{path="{safe_path}"}} {aggregate.count}',
                        f'portfolio_endpoint_errors_total{{path="{safe_path}"}} {aggregate.error_count}',
                        (
                            f'portfolio_endpoint_duration_ms_avg{{path="{safe_path}"}} '
                            f"{aggregate.total_duration_ms / aggregate.count:.2f}"
                        )
                        if aggregate.count
                        else f'portfolio_endpoint_duration_ms_avg{{path="{safe_path}"}} 0',
                    ]
                )
            return "\n".join(lines) + "\n"
