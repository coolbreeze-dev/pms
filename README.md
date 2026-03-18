# Household Portfolio Tracker

A household portfolio tracker built with FastAPI, React, and a portable SQLAlchemy data layer.

## Monorepo Layout

- `backend/`: FastAPI API, domain services, SQLAlchemy models, import pipeline, background jobs
- `frontend/`: React + TypeScript UI built with Vite
- `design-system/`: standalone Harbor npm package extracted from the app UI
- `ops/`: Docker, Caddy, and Litestream assets for hosted deployment hardening
- `shared/`: shared schema or generated artifacts

## Quick Start

### Seed Demo Data

```bash
./scripts/seed-demo.sh
```

### Backend

```bash
./scripts/dev-backend.sh
```

### Frontend

```bash
./scripts/dev-frontend.sh
```

The API binds to `http://127.0.0.1:8000` by default and the Vite dev server runs on `http://127.0.0.1:5173`.

### Run Both

```bash
./scripts/dev-mvp.sh
```

### Smoke Check A Running Deployment

```bash
./scripts/smoke-deploy.sh http://127.0.0.1:8000
```

## Easiest Cloud Deploy

The simplest durable low-cost path for this app is now:

- free compute on `Render`
- durable hosted `Neon Postgres`

- Blueprint file: `render.yaml`
- Step-by-step guide: `ops/RENDER_DEPLOY.md`
- One-click URL helper: `scripts/render-blueprint-url.sh`

Expected cost:

- `Render` free web service for the app
- `Neon` free Postgres for durable data

That means the app may sleep when idle, but your data does not depend on the app host's filesystem anymore.

## Local Node Toolchain

The repo now includes a workspace-local Node.js setup under `.tools/node` so you do not need a system-wide Node install for frontend work.

Examples:

```bash
./scripts/use-local-node.sh node -v
./scripts/test-frontend.sh
./scripts/build-frontend.sh
./scripts/test-e2e.sh
./scripts/test-backend.sh
```

## Harbor Design System Library

The extracted UI system is also packaged as a reusable npm library in `design-system/`.

Examples:

```bash
./scripts/build-design-system.sh
./scripts/pack-design-system.sh
```

The live showroom inside the app is available at `http://127.0.0.1:5173/design-system`.

## Environment Variables

Backend:

- `PORTFOLIO_DB_URL`: primary database URL. For durable hosted use, point this at Neon Postgres.
- `DATABASE_URL`: alias for `PORTFOLIO_DB_URL`
- `ENVIRONMENT`: `development` or `production`
- `FINNHUB_API_KEY`: optional live price/history source for US securities
- `ALPHA_VANTAGE_API_KEY`: optional dividend and corporate action source
- `FX_API_BASE_URL`: optional FX source override
- `CORS_ORIGINS`: JSON array of frontend origins, for example `["http://127.0.0.1:5173"]`
- `ALLOWED_HOSTS`: comma-separated hostnames accepted by the API when deployed behind a reverse proxy
- `FORCE_HTTPS`: redirect all HTTP traffic to HTTPS and emit HSTS headers when `true`
- `AUTH_PASSWORD`: optional single-password app lock for all protected API routes
- `AUTH_SECRET`: optional HMAC signing secret for auth tokens
- `AUTH_TOKEN_TTL_MINUTES`: token lifetime in minutes
- `LOG_LEVEL`: backend logging level
- `BROKERAGE_SYNC_PROVIDER`: `disabled`, `mock`, or `snaptrade`
- `BROKERAGE_SYNC_LOCAL_PROFILE_ID`: stable local household identifier used when registering a brokerage-sync user
- `BROKERAGE_SYNC_ACTIVITY_LOOKBACK_DAYS`: cash-activity import window for brokerage sync
- `SNAPTRADE_CLIENT_ID`: SnapTrade client id for live brokerage sync
- `SNAPTRADE_CONSUMER_KEY`: SnapTrade consumer key for live brokerage sync
- `SNAPTRADE_REDIRECT_URI`: optional redirect back to Settings after provider authorization

Frontend:

- `VITE_API_BASE_URL`: API base URL, defaults to `http://127.0.0.1:8000`

## Notes

- The MVP is still local-first, but it now supports optional password auth for protected API routes.
- For hosted durability, the recommended database is `Neon Postgres`. SQLite remains supported for local development, testing, and one-time migration.
- If API keys are missing, the backend falls back to cached or deterministic synthetic prices so the UI remains usable.
- Spreadsheet imports support CSV and Excel (`.xlsx` / `.xls`), including broker-specific position layouts for Vanguard, Fidelity, Schwab, Robinhood, Wealthfront, Empower, Principal, and Slavic 401k.
- Import previews now include reconciliation hints, suggested destination accounts, inferred-value warnings, and duplicate-lot detection before commit.
- Brokerage API sync now has a provider-agnostic foundation and a Settings workflow for connect plus sync.
- Live brokerage sync is currently implemented around SnapTrade, with a mock provider used for local automated tests.
- Brokerage sync currently imports linked accounts, positions, and cash-like activities such as deposits, withdrawals, and dividends.
- PDF imports are intentionally deferred to a later phase.
- Transactions and the `Investments` tab are now available for yearly net investment tracking.
- The Dashboard now includes TWRR, drawdown, concentration, benchmark spread, dividend outlook, category pulse, and QuantStats-style return quality views.
- The Settings page now surfaces runtime observability and ops guidance.

## Backup And Restore

Create a portable database backup:

```bash
./scripts/backup-db.sh
```

Restore from a backup file:

```bash
./scripts/restore-db.sh /path/to/backup.db-or-snapshot.json
```

For SQLite, backups are binary `.db` copies with a sidecar JSON manifest.

For Postgres/Neon, backups are JSON snapshots exported through the ORM schema.

If you already have local SQLite data and want to move it into Neon:

```bash
./scripts/migrate-to-neon.sh "postgresql://USER:PASSWORD@YOUR-NEON-HOST/neondb?sslmode=require"
```

Validate the local Litestream replica and restore workflow end to end:

```bash
./scripts/validate-litestream.sh
```

## Self-Hosted Deployment

The repo also includes a concrete self-hosted path under `ops/` if you later want your own VPS/container host:

- `ops/Dockerfile`: production image that builds the frontend, serves it from FastAPI, runs Alembic migrations on boot, and drops to a non-root user
- `ops/docker-compose.prod.yml`: app + Caddy + Litestream stack
- `ops/Caddyfile`: TLS termination and reverse proxy config
- `ops/.env.production.example`: production env template

Typical flow:

```bash
cp ops/.env.production.example ops/.env.production
./scripts/deploy-preflight.sh ops/.env.production
docker compose --env-file ops/.env.production -f ops/docker-compose.prod.yml up -d --build
./scripts/smoke-deploy.sh https://your-domain.example.com
```

To restore the SQLite file from Litestream into the named production volume before bringing the app up:

```bash
./scripts/restore-replica.sh ops/.env.production
```

## Migrations

Alembic migrations exist for both the initial schema and the brokerage-sync additions.

Example:

```bash
cd backend
.venv/bin/alembic upgrade head
```
