# Production Notes

This folder now contains a concrete hosted deployment path for a small VPS or container host:

- `Dockerfile`: builds the frontend, packages the FastAPI app, runs migrations on boot, and drops privileges to a non-root runtime user
- `docker-compose.prod.yml`: app + Caddy + Litestream stack
- `Caddyfile`: HTTPS termination and reverse proxy rules
- `.env.production.example`: deploy-time environment template
- `RENDER_DEPLOY.md`: the simplest managed deployment path for non-infra users

If you want the lowest-friction hosted option, use Render first. The Render Blueprint file lives at `render.yaml`.

## Compose Stack

The frontend depends on the local `harbor-design-system` package, so the production image builds `design-system/` before it builds the frontend.

Build and start from the repo root:

```bash
cp ops/.env.production.example ops/.env.production
./scripts/deploy-preflight.sh ops/.env.production
docker compose --env-file ops/.env.production -f ops/docker-compose.prod.yml up -d --build
```

The backend image includes:

- `HEALTHCHECK` against `/api/ready`
- `alembic upgrade head` on container start
- `uvicorn` with proxy headers enabled
- a non-root `appuser`

## Optional password auth

Set these environment variables for a single-password app lock:

```bash
AUTH_PASSWORD=choose-a-strong-local-password
AUTH_SECRET=optional-override-for-token-signing
AUTH_TOKEN_TTL_MINUTES=720
```

`/api/health`, `/api/ready`, `/api/auth/login`, `/api/auth/session`, and `/api/ops/metrics` stay reachable without a bearer token so deployment and metrics checks can still run.

In production you should also set:

```bash
ENVIRONMENT=production
ALLOWED_HOSTS=portfolio.example.com
FORCE_HTTPS=true
```

Those enable trusted-host filtering plus HTTPS redirect/HSTS behavior in the app itself.

## Database and backups

- The app uses SQLite in WAL mode.
- Litestream replication is configured in `ops/litestream.yml`.
- Mount the SQLite database on persistent storage in production.
- Local backup and restore workflows are implemented via `./scripts/backup-db.sh` and `./scripts/restore-db.sh`.
- A local replica-and-restore validation is available via `./scripts/validate-litestream.sh`.
- The compose stack mounts the database at `/data/portfolio.db` and runs Litestream against the same named volume.

## Litestream restore workflow

Restore the named production volume from the configured replica before first boot or disaster recovery:

```bash
./scripts/restore-replica.sh ops/.env.production
```

Under the hood, that runs the `restore` service from `docker-compose.prod.yml`, which writes `/data/portfolio.db` into the persistent `portfolio_data` volume.

For a local dry run against a file replica, use:

```bash
./scripts/validate-litestream.sh
```

## Deployment verification

After startup, run:

```bash
./scripts/smoke-deploy.sh https://your-hostname.example.com
./scripts/test-e2e.sh
```

If auth is enabled, export `PORTFOLIO_APP_PASSWORD` before running the smoke test.

## Migrations

Alembic migrations now exist for the initial schema and the brokerage-sync metadata.

Typical workflow:

```bash
cd backend
.venv/bin/alembic upgrade head
```
