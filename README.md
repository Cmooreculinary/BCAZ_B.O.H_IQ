# BCAz B.O.H Global IQ

The back office, rebuilt from the trenches.

BCAz B.O.H Global IQ is a tenant-scoped hospitality operating system connecting purchasing, Dock receiving, invoice matching, inventory movements, recipes, production, tasks, and evidence-backed operating questions.

## Recovered beta scope

- Tenant-scoped authentication and role permissions
- Purchasing and procure-to-pay timeline
- Dock receiving completion with idempotent inventory ledger posting
- Invoice duplicate detection and three-way matching
- Inventory calculations and variance controls
- Recipe economics with mandatory allergen-liability language
- Ranked command board and auditable actions
- Global IQ answers tied to source records
- File, memory, and MongoDB repository adapters
- PWA shell and offline-operation queue
- Explicit CORS allowlist, signed sessions, request IDs, and structured errors

## Repository layout

```text
apps/
  api/    FastAPI service for Render
  web/    React + Vite interface for Vercel
docs/
  BUILD_SCOPE.md
  DEPLOYMENT.md
render.yaml
docker-compose.yml
```

## Local development

### API

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt
read -s -p "Local demo password: " DEMO_PASSWORD; echo
export DEMO_PASSWORD
APP_STORAGE=memory .venv/bin/uvicorn app.main:app --app-dir apps/api --reload
```

The API is available at `http://127.0.0.1:8000`; health is at `/api/v1/health`.

### Web

```bash
cd apps/web
npm ci
npm run dev
```

The web application is available at `http://127.0.0.1:5173`.

Before starting the local API, export `DEMO_PASSWORD` with a private local value containing at least 12 characters. The local owner email is `owner@bcaz.example`. Production has no hardcoded password.

## Verification

```bash
.venv/bin/pytest apps/api/tests -q
cd apps/web
npm test
npm run build
```

## Deployment

The API deploys as a Render Web Service from `apps/api`. The frontend deploys separately on Vercel from `apps/web`. Exact fields and required environment variables are in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

### Render Blueprint

The root [`render.yaml`](render.yaml) is the deployment recipe for the API. It tells Render which branch and directory to use, how to install and start the FastAPI service, which health check to monitor, and which configuration values are required. Keeping this configuration in GitHub makes the deployment repeatable and reviewable.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Cmooreculinary/BCAZ_B.O.H_IQ)

During Blueprint deployment, Render requests these private values:

- `MONGODB_URI`: the MongoDB Atlas connection string
- `CORS_ORIGINS`: `http://localhost:5173` temporarily, then the exact Vercel production origin
- `BOOTSTRAP_ADMIN_EMAIL`: the approved administrator email
- `BOOTSTRAP_ADMIN_PASSWORD`: a unique password containing at least 12 characters

Do not paste those secrets into GitHub or chat. Nothing becomes live until an authorized user reviews the Blueprint, supplies the private values in Render, and clicks **Deploy Blueprint**. The Blueprint deploys the API only; the Vercel frontend is a separate deployment.

Never commit production credentials. Never use wildcard CORS. Allergen information is operational support only and never a safety guarantee.
