# AgentCart implementation plan

**Status:** Active  
**Date:** 2026-10-17  
**Environment notes:** Empty workspace. Node 24.18.1, npm 11.16.0, Python 3.14 default, **Python 3.12.13 via uv**. No Docker, no local PostgreSQL, no PayPal or Gemini keys in the environment.

## Compatibility decisions

| Requirement | Local choice | Why |
|---|---|---|
| PostgreSQL | SQLAlchemy + `DATABASE_URL`. Default **SQLite** file `backend/agentcart.db`. PostgreSQL supported in production. | PostgreSQL client and Docker are not installed. SQLite lets the demo run immediately. |
| Python 3.11/3.12 | **3.12** via `uv` | System Python is 3.14; 3.12 matches the spec. |
| Docker Compose | Provided for PostgreSQL | Optional. Not required for local demo. |
| PayPal currency | Catalog in **INR**. Sandbox charge in **USD** using a documented conversion rate. | Typical Sandbox merchant accounts are USD. UI labels both amounts. |
| Auth | **Demo session** UUID cookie / header | Prototype scope. Not production identity. |

## Folder structure

```
agent_cart/
  backend/          FastAPI, SQLAlchemy, Alembic, ranking, AI, PayPal
  frontend/         Next.js App Router
  docs/             Architecture, ranking, PayPal, demo, tests
  postman/          Shareable API collection
  docker-compose.yml
```

## API contracts

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + provider configuration flags (no secrets) |
| GET | `/api/products` | Catalog search, filters, pagination |
| GET | `/api/products/{id}` | Product detail |
| POST | `/api/agent/search` | Extract requirements, search, filter, rank |
| POST | `/api/agent/message` | Follow-up turn on a session |
| POST | `/api/agent/compare` | Compare selected products |
| POST | `/api/agent/rerank` | Recalculate ranking from stored requirements + weights |
| GET | `/api/sessions/{id}` | Session, messages, requirements |
| GET | `/api/sessions/{id}/recommendations` | Latest recommendation run |
| POST | `/api/checkout/create-order` | Server-priced PayPal order |
| POST | `/api/checkout/capture-order` | Capture after approval |
| GET | `/api/orders` | Session orders |
| GET | `/api/orders/{id}` | Order + verified payment state |
| GET | `/api/settings/public` | Non-secret settings |

## Database schema (core)

- `products` — demo catalog
- `shopping_sessions` — demo session id
- `conversation_messages`
- `shopping_requirements` — JSON snapshot
- `recommendation_runs` / `recommendation_results`
- `orders`
- `payment_attempts` — create/capture/refund attempts, idempotency keys

## AI architecture

1. **Requirement extraction** — Gemini structured JSON when `GEMINI_API_KEY` is set; otherwise labelled **rule-based demo mode**.
2. **Tools** executed only on the server: `search_products`, `get_product_details`, `compare_products`, `validate_constraints`, `rank_products`, `explain_recommendation`, `create_checkout` (checkout still requires explicit user confirmation on the client).
3. LLM never writes SQL or calls PayPal with client-supplied amounts.
4. Ranking is **deterministic Python**, independently tested.

## Ranking (summary)

1. Apply **hard constraints** (budget, category, min RAM, excluded brands, availability).
2. Score remaining products on available numeric attributes only.
3. Missing attributes are `null`, excluded from the weighted average, and disclosed.
4. Weights are user-adjustable; rerank does not require an LLM.

## Payments

Official PayPal REST:

- `POST {PAYPAL_BASE_URL}/v1/oauth2/token`
- `POST {PAYPAL_BASE_URL}/v2/checkout/orders`
- `POST {PAYPAL_BASE_URL}/v2/checkout/orders/{id}/capture`

Success is stored only after a verified capture response. Redirects are navigation, not proof of payment.

## Implementation order

1. Plan (this file)
2. Design system + landing + catalog UI
3. Backend models, seed, filter/rank, APIs
4. AI provider + tools + fallback
5. PayPal create/capture + tests
6. Polish, lint, pytest, Next production build
7. README, architecture diagram, demo script

## Credentials needed (not present at plan time)

- `GEMINI_API_KEY` — optional; app falls back to rule-based mode
- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` — required for real Sandbox checkout
- `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`

## Risks

- PayPal Sandbox cannot be executed here until credentials are provided.
- Gemini extraction cannot be live-tested without an API key.
- SQLite is the local default; production should use PostgreSQL.
