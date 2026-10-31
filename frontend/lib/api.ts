import { demoSessionId } from "./utils";
import type { Health, Order, Product, PublicSettings, RankedProduct, RankingResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (typeof window !== "undefined") {
    headers.set("X-Demo-Session", demoSessionId());
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (data as { detail?: unknown }).detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail && "message" in detail
          ? String((detail as { message: string }).message)
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  settings: () => request<PublicSettings>("/api/settings/public"),
  products: (params?: Record<string, string>) => {
    const search = new URLSearchParams(params);
    const suffix = search.toString() ? `?${search}` : "";
    return request<{ total: number; items: Product[] }>(`/api/products${suffix}`);
  },
  product: (id: string) => request<Product>(`/api/products/${id}`),
  search: (message: string, sessionId?: string | null) =>
    request<RankingResponse>("/api/agent/search", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId || undefined }),
    }),
  followUp: (sessionId: string, message: string) =>
    request<RankingResponse>("/api/agent/message", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, message }),
    }),
  rerank: (sessionId: string, weights: RankingResponse["weights"]) =>
    request<RankingResponse>("/api/agent/rerank", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, weights }),
    }),
  compare: (productIds: string[], sessionId?: string | null) =>
    request<{ items: RankedProduct[]; tradeoff_summary: string; missing_ids: string[]; methodology: string }>(
      "/api/agent/compare",
      {
        method: "POST",
        body: JSON.stringify({ product_ids: productIds, session_id: sessionId || undefined }),
      },
    ),
  createSession: () => request<{ id: string; title: string }>("/api/sessions", { method: "POST" }),
  sessions: () => request<{ items: { id: string; title: string; status: string }[] }>("/api/sessions"),
  session: (id: string) => request<{ id: string; title: string; messages: { role: string; content: string }[]; requirement: unknown }>
    (`/api/sessions/${id}`),
    createOrder: (
      productId: string,
      sessionId: string,
      idempotencyKey: string,
    ) =>
      request<{
        order: Order;
        approval_url: string;
        pricing_note: string;
        sandbox: boolean;
        duplicate?: boolean;
      }>("/api/checkout/create-order", {
        method: "POST",
        body: JSON.stringify({
          product_id: productId,
          session_id: sessionId,
          idempotency_key: idempotencyKey,
        }),
      }),

    createCartOrder: (
      items: { product_id: string; quantity: number }[],
      sessionId: string,
      idempotencyKey: string,
    ) =>
      request<{
        order: Order;
        approval_url: string;
        pricing_note: string;
        sandbox: boolean;
        duplicate?: boolean;
      }>("/api/checkout/create-order", {
        method: "POST",
        body: JSON.stringify({
          items,
          session_id: sessionId,
          idempotency_key: idempotencyKey,
        }),
      }),

  captureOrder: (paypalOrderId: string, sessionId: string) =>
    request<{ order: Order; duplicate: boolean }>("/api/checkout/capture-order", {
      method: "POST",
      body: JSON.stringify({ paypal_order_id: paypalOrderId, session_id: sessionId }),
    }),
  cancelOrder: (paypalOrderId: string, sessionId: string) =>
    request<{ order: Order }>("/api/checkout/cancel", {
      method: "POST",
      body: JSON.stringify({ paypal_order_id: paypalOrderId, session_id: sessionId }),
    }),
    orders: () => request<{ items: Order[]; sandbox: boolean }>("/api/orders"),
    order: (id: string) => request<{ order: Order; sandbox: boolean }>(`/api/orders/${id}`),

  // Verify PayPal payment without initiating another capture
  reconcileOrder: (id: string) =>
    request<{
      order: Order;
      reconciliation: "already_paid" | "paid" | "unresolved";
      paypal_status?: string | null;
      message?: string;
      sandbox: boolean;
    }>(`/api/orders/${id}/reconcile`, {
      method: "POST",
    }),
};

export const EXAMPLES = [
  {
    href: "/shop?q=" + encodeURIComponent("Find me the best laptop for coding under ₹70,000. I need at least 16 GB RAM, good battery life, a decent display, and something that will last through college."),
    label: "Find a laptop for coding under ₹70,000.",
  },
  {
    href: "/shop?q=" + encodeURIComponent("Find wireless headphones under ₹8,000 with good battery life."),
    label: "Find wireless headphones under ₹8,000 with good battery life.",
  },
  {
    href: "/shop?q=" + encodeURIComponent("Find a monitor for programming and productivity under ₹20,000."),
    label: "Find a monitor for programming and productivity.",
  },
  {
    href: "/compare?ids=prod-laptop-northline-14,prod-laptop-proair-14",
    label: "Compare two products and explain which is better for my needs.",
  },
];
