# AgentCart Backend

FastAPI service powering AgentCart:
- **Curated Catalog:** 38 labelled hardware SKUs with realistic specifications and edge cases (unknown specs, unavailable items).
- **AI & Rule-Based Intent Extraction:** Extracts budget, category, minimum RAM/storage, use cases, and excluded brands with conversational multi-turn context.
- **Deterministic Python Ranking:** Hard constraints evaluated first; weighted scoring on verified numeric attributes only (unknown attributes are never guessed).
- **Official PayPal REST Sandbox Integration:** Server-side order creation, INR-to-USD conversion at documented demo rate, buyer approval redirects, and verified server capture.

---

## Quickstart

### Prerequisites

- Python 3.12 (managed via `uv` or standard virtual environment)

### Run Locally

```bash
# Install dependencies
uv sync --group dev

# Start development server
uv run uvicorn app.main:app --reload --port 8000

# Run automated tests
uv run pytest
```

Interactive API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)  
Health status: [http://localhost:8000/api/health](http://localhost:8000/api/health)  
Public settings: [http://localhost:8000/api/settings/public](http://localhost:8000/api/settings/public)

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service health, provider flags, database type |
| GET | `/api/settings/public` | Public settings, currencies, demo FX rate |
| GET | `/api/products` | Catalog listings with category/brand/price/availability filters |
| GET | `/api/products/{id}` | Product specification details |
| POST | `/api/agent/search` | Natural language requirement extraction and ranking |
| POST | `/api/agent/message` | Follow-up conversational turn on session |
| POST | `/api/agent/rerank` | Deterministic score recomputation with custom weights |
| POST | `/api/agent/compare` | Multi-product side-by-side spec comparison |
| POST | `/api/sessions` | Create or get demo session |
| GET | `/api/sessions/{id}` | Session message history and active requirements |
| GET | `/api/sessions/{id}/recommendations` | Latest recommendation run |
| POST | `/api/checkout/create-order` | Server-priced PayPal Sandbox order creation |
| POST | `/api/checkout/capture-order` | PayPal Sandbox order capture verification |
| POST | `/api/checkout/cancel` | Cancel pending order |
| GET | `/api/orders` | Session order history |
| GET | `/api/orders/{id}` | Order payment status and capture ID |

---

## Configuration & Environment

Set in repo root `.env` (refer to `.env.example`):

- `DATABASE_URL`: Defaults to `sqlite+pysqlite:///./agentcart.db` for instant local setup. Supports PostgreSQL for production (`postgresql+psycopg://...`).
- `GEMINI_API_KEY`: Optional. If unset, the service runs in verified rule-based extraction mode.
- `PAYPAL_CLIENT_ID` & `PAYPAL_CLIENT_SECRET`: Optional. If unset, checkout endpoints refuse order creation with HTTP 503 (`paypal_not_configured`), never fabricating false success.
- `PAYPAL_INR_PER_USD`: Fixed demo conversion rate (default `83.00`).
