# Render + Neon Deploy Guide

This is the easiest path if you want:

- free app hosting to start
- durable data
- very little infrastructure work

The recommended shape is:

- `Render` free web service for the app
- `Neon` free Postgres for the database

That means:

- your app may sleep when idle
- your data will not be tied to the app host's local disk
- redeploying the app will not wipe your portfolio data

## What You Need

1. This repo pushed to GitHub
2. A free `Neon` account
3. A free `Render` account

## Step 1. Create a Neon Database

In Neon:

1. Create a new project
2. Open the connection details
3. Copy the pooled Postgres connection string

It should look roughly like:

```text
postgresql://USER:PASSWORD@ep-example-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

Important:

- use the pooled connection string
- keep `sslmode=require`

## Step 2. If You Have Local Data, Migrate It to Neon

If you already imported holdings locally and want to keep them:

```bash
./scripts/migrate-to-neon.sh "postgresql://USER:PASSWORD@ep-example-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

That copies your current local SQLite portfolio into Neon.

## Step 3. Open the Render Blueprint

Generate the Blueprint URL:

```bash
./scripts/render-blueprint-url.sh
```

Then open the printed URL in your browser.

Render will read `render.yaml` from GitHub.

## Step 4. Fill the Required Secrets in Render

Render will ask you for secrets. Set:

- `PORTFOLIO_DB_URL`
  Use your Neon connection string
- `AUTH_PASSWORD`
  Choose the password you will use to unlock the app

Render will generate `AUTH_SECRET` automatically.

## Step 5. Deploy

Keep the defaults:

- service type: `Web Service`
- runtime: `Docker`
- plan: `Free`

Then click `Apply`.

When deployment finishes, you will get a URL like:

```text
https://your-service-name.onrender.com
```

## Step 6. Verify It

Run:

```bash
PORTFOLIO_APP_PASSWORD='your-password' ./scripts/smoke-deploy.sh https://your-service-name.onrender.com
```

Then open the app in a browser and log in.

## What To Expect On Free Hosting

This setup is durable, but not always-on.

That means:

- Render may spin the app down when idle
- the first request after idle may be slow
- Neon keeps the data, so your portfolio is still there

## Updating the App Later

Once GitHub and Render are connected:

```bash
git add .
git commit -m "Your update"
git push
```

Render will redeploy automatically.

Your data remains in Neon.

## Backup Habit

For an extra safety layer, you can still export a portable snapshot:

```bash
./scripts/backup-db.sh
```

Because the app is using Neon, that backup will be a JSON snapshot instead of a SQLite `.db` file.

## If You Want a Paid Upgrade Later

The first upgrade I would suggest is:

- keep Neon
- move Render from `Free` to a paid always-on plan

That gives you the same durable storage model, just with fewer cold starts.
