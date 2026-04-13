# TradeX — production deployment (Vercel + Render)

This project is a **Next.js** frontend (`frontend/`) and a **FastAPI** backend (`backend/`). Do not rebuild the app for deploy: configure environment variables, run the production build once locally if you like, then connect the hosts.

---

## 1. Environment variables

### Frontend (Vercel) — required for a working app

| Variable | Required | Example / notes |
|----------|----------|------------------|
| `NEXT_PUBLIC_API_URL` | **Yes** (production) | `https://tradex-api.onrender.com` — no trailing slash. Browser calls the API here. |
| `NEXT_PUBLIC_SITE_URL` | Recommended | `https://your-domain.vercel.app` or your custom domain — sitemap, OG, canonical URLs. If unset on Vercel, `VERCEL_URL` is used when present. |

### Backend (Render) — minimum for a safe public API

| Variable | Required | Example / notes |
|----------|----------|------------------|
| `TRADEX_ENVIRONMENT` | Yes | `production` |
| `TRADEX_JWT_SECRET` | **Yes** in production | Long random string; app refuses to start without it when `production`. |
| `TRADEX_CORS_ORIGINS` | **Yes** for custom domains | Comma-separated, e.g. `https://tradex.vercel.app,https://www.yourdomain.com` |
| `TRADEX_CORS_ALLOW_VERCEL_HOSTS` | Optional | `true` — allows `https://*.vercel.app` (previews + default Vercel URLs) via regex. |
| `PORT` | Auto on Render | Injected by Render; do not set manually unless you know why. |

### Backend — strongly recommended for real users / exchange features

| Variable | Notes |
|----------|--------|
| `TRADEX_EXCHANGE_FERNET_KEY` | Fernet key for encrypting per-user exchange API secrets. Generate locally: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `TRADEX_DATABASE_URL` or platform `DATABASE_URL` | **Ephemeral filesystem:** SQLite on Render’s disk is wiped on redeploy unless you use a **persistent disk** or **Postgres**. The backend ships `psycopg` and normalizes `postgres://` / `postgresql://` to `postgresql+psycopg://`. |
| `TRADEX_LOG_LEVEL` | `INFO` or `WARNING` in production. |

### Backend — optional

| Variable | Notes |
|----------|--------|
| `TRADEX_JWT_ACCESS_DAYS` | Default `14`. |
| `TRADEX_OLLAMA_*` | Local LLM only; not needed on a typical cloud API. |
| `TRADEX_CORS_ALLOW_ALL` | Staging only; disables credential-friendly CORS. |

Copy from `frontend/.env.example` and `backend/.env.example` and fill values for each platform.

---

## 2. Exact run / build commands

### Backend (local)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**Local dev (optional multi-worker / same as many PaaS scripts):**

```bash
python run.py
```

**Production-style (matches Render `startCommand`):**

```bash
# Linux/macOS/Git Bash — PORT is set by the host on Render
export PORT=10000
uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
```

**Windows PowerShell:**

```powershell
$env:PORT = "10000"
uvicorn main:app --host 0.0.0.0 --port $env:PORT --proxy-headers --forwarded-allow-ips '*'
```

Health check: `GET http://127.0.0.1:10000/health` (or your `PORT`).

### Frontend (local)

```bash
cd frontend
npm install
# Point at your API (local or deployed):
# NEXT_PUBLIC_API_URL=http://127.0.0.1:10000
npm run dev
```

**Production build:**

```bash
cd frontend
npm install
# Required for production bundle (no localhost fallback in the client):
set NEXT_PUBLIC_API_URL=https://your-api.onrender.com
npm run build
```

PowerShell: `$env:NEXT_PUBLIC_API_URL="https://..."; npm run build`

**Start production server locally (after `npm run build`):**

```bash
npx next start
```

---

## 3. Exact steps — frontend on Vercel

1. Push the repo to GitHub/GitLab/Bitbucket (include the `tradex/` tree as you use it today).
2. [Vercel](https://vercel.com) → **Add New** → **Project** → import the repo.
3. **Root Directory**: set to the folder that contains `package.json` for the app, e.g. `tradex/frontend` if the monorepo root is above that.
4. **Framework Preset**: Next.js (auto).
5. **Build & Output**: default `npm run build` / `.next` is fine (no `standalone` output in-repo — avoids flaky Windows/OneDrive builds; re-enable in `next.config.ts` only if you ship a Docker image).
6. **Environment Variables** (Production + Preview as needed):
   - `NEXT_PUBLIC_API_URL` = your Render API origin, e.g. `https://tradex-api.onrender.com`
   - `NEXT_PUBLIC_SITE_URL` = your Vercel URL or custom domain, e.g. `https://tradex.vercel.app`
7. Deploy. After the API URL exists, **redeploy** the frontend if you change `NEXT_PUBLIC_API_URL` (it is inlined at build time).
8. Confirm routes: `/` (landing), `/login`, `/signup`, `/dashboard`, `/portfolio`, `/backtest` (sidebar: Backtesting; `/backtesting` redirects), `/settings`.

---

## 4. Exact steps — backend on Render

1. Push the same repo; note paths below relative to repo root.
2. **Option A — Blueprint**: Render → **New** → **Blueprint** → connect repo. Render’s default is a `render.yaml` at the **repository root**; this repo keeps the spec at `tradex/render.yaml` — either **copy/symlink** it to the root for Blueprint discovery, or create the web service manually (**Option B**). If the repo root is `tradex/` (this folder is the git root), Blueprint will find `render.yaml` as-is. Edit `rootDir: backend` if your backend folder path differs.
3. **Option B — Web Service manually**:
   - **Root Directory**: `tradex/backend` (or `backend` if repo root is `tradex`).
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**:  
     `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
   - **Health check path**: `/health`
4. In the service **Environment** tab, set at least:
   - `TRADEX_ENVIRONMENT=production`
   - `TRADEX_JWT_SECRET` = secret value
   - `TRADEX_CORS_ORIGINS` = your Vercel production URL (and custom domain if any)
   - `TRADEX_CORS_ALLOW_VERCEL_HOSTS=true` if you rely on `*.vercel.app` previews
5. Optional: add **Postgres** (or persistent disk) and let Render set `DATABASE_URL`, or set `TRADEX_DATABASE_URL` yourself.
6. Deploy; open `https://<your-service>.onrender.com/health` — expect JSON `status: ok`.
7. Put that same origin (no path) into Vercel as `NEXT_PUBLIC_API_URL` and redeploy the frontend.

---

## 5. Files to review or update before go-live

| File | Why |
|------|-----|
| `render.yaml` | Region, plan, service name, `rootDir`, `startCommand`, non-secret env defaults. |
| `frontend/next.config.ts` | `/backtesting` → `/backtest` redirect; re-enable `standalone` only if you Dockerize. |
| `frontend/.env.local` (local only) | Never commit secrets; use Vercel UI for deploy env. |
| `backend/.env` (local only) | Production secrets only on Render. |
| `TRADEX_CORS_ORIGINS` | Must include every browser origin that calls the API (production + staging domains). |
| `NEXT_PUBLIC_SITE_URL` | Avoid wrong canonical/OG URLs on a custom domain. |
| DNS | Custom domain on Vercel + optional API subdomain if you terminate TLS in front of Render. |

---

## 6. Production connection & errors

- All browser API traffic goes through `frontend/lib/api.ts` using `getPublicApiBaseUrl()` from `frontend/lib/env.ts` (`NEXT_PUBLIC_API_URL`). There is **no** production fallback to localhost.
- If `NEXT_PUBLIC_API_URL` is missing in production, users see a clear error from `mapNetworkError` / `formatUserFacingApiError` (transport and misconfiguration).
- Backend CORS must allow the frontend origin; JWT cookies are not used for API auth in the described flow — localStorage bearer token — but CORS still applies to `fetch`.

---

## 7. Remaining blockers before “real” public launch

1. **`TRADEX_JWT_SECRET`** must be set on Render for `TRADEX_ENVIRONMENT=production` or the process exits at startup.
2. **Data persistence**: default SQLite on a disposable disk loses data on redeploy unless you add **Postgres** (recommended) or a **Render disk** mount pointed at your DB path.
3. **`NEXT_PUBLIC_API_URL`** must be set on Vercel for every environment that should talk to the API; change requires **rebuild**.
4. **CORS**: every new frontend URL (custom domain, preview) must be allowed via `TRADEX_CORS_ORIGINS` and/or `TRADEX_CORS_ALLOW_VERCEL_HOSTS`.
5. **Exchange / encryption**: without `TRADEX_EXCHANGE_FERNET_KEY`, features that store exchange keys may be limited or fail — generate and set for production.
6. **Cold starts / free tier**: first request after idle can be slow; upgrade plan or keep-alive if that matters for demos.

---

## 8. Quick verification checklist

- [ ] `GET https://<api>/health` → `200`, JSON `status: ok`
- [ ] Vercel site loads `/` without console errors for API base
- [ ] Signup + login + dashboard load data (CORS + JWT OK)
- [ ] `/backtesting` hits a 308/redirect to `/backtest`
- [ ] `NEXT_PUBLIC_SITE_URL` matches what you share publicly (links, OG)

When this checklist passes, you are ready to point a custom domain at Vercel and optionally at the API.
