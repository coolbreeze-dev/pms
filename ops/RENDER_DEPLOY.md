# Render Deploy Guide

This is the easiest hosted path for this app right now.

Why this is the recommended option:

- It can deploy directly from this repo
- It supports a persistent disk for the SQLite database
- It gives you HTTPS automatically
- It rebuilds on every `git push`
- It keeps the app as one service instead of splitting frontend and backend

## Expected Cost

Render's official pricing page currently lists:

- `Starter` web service: `$7/month`
- persistent disk: `$0.25/GB/month`

This app is configured for:

- `1` Starter web service
- `1 GB` persistent disk

That puts the expected starting cost at about `$7.25/month`.

## One-Time Setup

### 1. Put this repo on GitHub

If you do not already have a remote:

```bash
git init
git add .
git commit -m "Initial app commit"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

If the repo already exists on GitHub, just push your latest code there.

### 2. Generate your one-click Render link

```bash
./scripts/render-blueprint-url.sh
```

That prints a Render Blueprint URL you can open in your browser.

## Deploy Steps

### 1. Open the Blueprint link

Render will read the checked-in `render.yaml` file and prefill the service configuration.

### 2. Keep the defaults unless you know you want something different

Recommended:

- Service type: `Web Service`
- Runtime: `Docker`
- Plan: `Starter`
- Disk: keep the attached persistent disk

### 3. Fill the one required secret

Render will ask for:

- `AUTH_PASSWORD`

Choose a password you will remember. This becomes the lock screen password for the app.

Render will generate `AUTH_SECRET` automatically from the Blueprint.

### 4. Click `Apply`

Render will build the Docker image, start the app, mount the disk, and give you a public URL like:

```text
https://your-service-name.onrender.com
```

## After Deploy

Run the smoke test against your public URL:

```bash
PORTFOLIO_APP_PASSWORD='your-password' ./scripts/smoke-deploy.sh https://your-service-name.onrender.com
```

If that passes, open the site in a browser and log in with the same password.

## First-Time App Use

After login:

1. Go to `Settings`
2. Import your CSV or Excel holdings
3. Refresh prices
4. Review the dashboard

## Updating the App Later

Once GitHub and Render are connected, updates are simple:

```bash
git add .
git commit -m "Your update"
git push
```

Render will auto-deploy the new version.

## Backups

Render keeps the persistent disk mounted, but you should still use Litestream replication for off-host recovery later.

For now, the simplest backup habit is:

```bash
./scripts/backup-db.sh
```

## If You Want a Custom Domain Later

You can add that in the Render dashboard after the app is live. The app will still work fine on the default `onrender.com` URL.
