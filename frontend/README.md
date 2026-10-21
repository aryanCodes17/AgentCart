# AgentCart Frontend

The web interface for AgentCart — an intent-led shopping assistant with deterministic constraint validation, transparent recommendation scoring, and PayPal Sandbox checkout.

Built with **Next.js 16** (App Router, Turbopack), **React 19**, **Tailwind CSS 4**, and **TypeScript**.

---

## Getting Started

### Prerequisites

- Node.js 20+ (recommended: Node 22 or 24)
- npm 10+
- Running backend on `http://localhost:8000` (or configured via `NEXT_PUBLIC_API_URL`)

### Installation & Run

```bash
# Install dependencies
npm install

# Start local dev server (Turbopack)
npm run dev

# Run ESLint
npm run lint

# Production build
npm run build
```

Open [http://localhost:3000](http://localhost:3000) to view AgentCart.

---

## Application Routes

- `/` — Landing page highlighting system architecture, feature highlights, and sample shopping intents.
- `/shop` — Searchable catalog with natural language intent extraction, category filtering, deterministic constraint filters, weight tuning sliders, and multi-turn refinement.
- `/products/[id]` — Product detail page showing catalog specs (unknown fields omitted, not guessed) and PayPal Sandbox checkout initiation.
- `/compare` — Multi-product side-by-side comparison with trade-off explanations and component scoring.
- `/orders` — Session-scoped order history with PayPal order ID and capture ID verification.
- `/checkout/success` — PayPal Sandbox return and cancellation handler; triggers server-side capture and displays verified payment state.
- `/settings` — Public system configuration and connectivity monitor.

---

## Environment Variables

Configure in repo root `.env` or `frontend/.env.local`:

```ini
# Backend API URL (default: http://localhost:8000)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional GitHub repository link
NEXT_PUBLIC_GITHUB_URL=https://github.com/your-org/agentcart
```

---

## Design System & Tokens

Defined in `app/globals.css`:
- **Paper Background:** `#f4f1ea`
- **Elevated Surfaces:** `#fbf9f4`
- **Ink Primary:** `#1c1917`
- **Ink Muted:** `#57534e`
- **Border Lines:** `#e7e0d4`
- **Accent Primary:** `#1d4ed8`
- **Border Radius:** `10px`
