# AgentCart

Intent-led shopping prototype for the PayPal AI Hackathon.

You describe what you need. The backend extracts requirements, searches a **labelled demo catalog**, applies **hard constraints in Python**, and ranks only on verified attributes. Checkout uses **official PayPal REST** (Sandbox) with **server-side prices**. Payment is marked paid only after a verified capture.

This is not a live store. Catalog prices are demo data. Success is never faked.

## What works without extra keys

- Catalog browse and product detail
- Natural-language search in **rule-based demo mode**
- Deterministic ranking, compare, and rerank
- Health flags (`GET /api/health`)
- Checkout **refuses** to create a PayPal order until Sandbox credentials are set (HTTP 503)

## Optional live integrations

| Variable | Effect if missing |
|---|---|
| `GEMINI_API_KEY` | Requirement extraction stays rule-based and is labelled as such |
| `PAYPAL_CLIENT_ID` + `PAYPAL_CLIENT_SECRET` | Create-order returns `paypal_not_configured` |

## Local setup

Requires **Python 3.12** (this repo uses `uv`) and **Node.js 20+**.

```bash
copy .env.example .env
# edit .env — leave PayPal/Gemini blank to run in demo mode
```

### Backend

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000/docs  
Health: http://localhost:8000/api/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:3000

### Tests

```bash
cd backend
uv run pytest -q
```

Frontend lint/build: `npm run lint` and `npm run build` in `frontend/`.

### Optional PostgreSQL

`docker-compose.yml` starts Postgres 16. Set `DATABASE_URL` in `.env` to the PostgreSQL URL. SQLite is the default for the local demo.

## PayPal Sandbox

1. Create Sandbox REST credentials in the PayPal Developer dashboard.
2. Set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`.
3. Catalog amounts are INR. Sandbox charges **USD** using `PAYPAL_INR_PER_USD` (documented demo rate, not a live FX feed).
4. Buyer approval happens on PayPal. AgentCart captures on `/checkout/success` and stores `paid` only with a capture id.

## Project layout

```
backend/     FastAPI, ranking, AI tools, PayPal client
frontend/    Next.js App Router
docs/        Plan and implementation status
```

See [docs/implementation-status.md](docs/implementation-status.md) for the audit, gaps, and milestone log.
