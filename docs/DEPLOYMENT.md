# Deployment — BCAz B.O.H Global IQ

## Render API service

Create **New → Web Service**, select `Cmooreculinary/BCAZ_B.O.H_IQ`, and use:

| Render field | Exact value |
| --- | --- |
| Name | `bcaz-boh-iq-api` |
| Region | `Virginia` |
| Branch | `feature/bcaz-boh-global-iq` |
| Root Directory | `apps/api` |
| Language | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/v1/health` |
| Instance Type | `Free` for beta verification |

Required environment variables:

| Key | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.11.11` |
| `APP_ENV` | `production` |
| `APP_STORAGE` | `mongo` |
| `MONGODB_URI` | MongoDB connection string entered as a secret |
| `MONGODB_DATABASE` | `bcaz_boh_iq` |
| `AUTH_SECRET` | Random secret with at least 32 characters |
| `CORS_ORIGINS` | Exact production origin displayed by Vercel |
| `BOOTSTRAP_ADMIN_EMAIL` | `owner@bcaz.example` or the approved administrator email |
| `BOOTSTRAP_ADMIN_PASSWORD` | Unique password with at least 12 characters |
| `SEED_DEMO_DATA` | `true` for the controlled beta dataset |
| `ACCESS_TOKEN_MINUTES` | `480` |

Do not include quotes around values. Do not use `*` for `CORS_ORIGINS`.

The included `render.yaml` contains the same service configuration. Environment secrets remain manual by design.

## Vercel frontend

Import the same repository into Vercel and use:

| Vercel field | Exact value |
| --- | --- |
| Branch | `feature/bcaz-boh-global-iq` |
| Root Directory | `apps/web` |
| Framework Preset | `Vite` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

Set `VITE_API_URL` to `https://bcaz-boh-iq-api.onrender.com/api/v1` after Render confirms that service URL.

After Vercel deploys, replace Render's `CORS_ORIGINS` with the exact Vercel production URL and redeploy Render. If an environment variable changes in Vercel, redeploy without cache. If Python dependencies change, clear Render's build cache before redeploying.

## Post-deployment verification

1. Open the Render service's `/api/v1/health` endpoint and confirm `status` is `healthy`.
2. Open its `/api/v1/readiness` endpoint and confirm `database_connected` is `true`.
3. Open the Vercel application and sign in with the configured bootstrap administrator.
4. Confirm the command board, procurement timeline, records table, and Global IQ evidence response load.
5. Confirm the browser console has no CORS errors.
