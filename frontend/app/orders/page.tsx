"use client";

import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Order } from "@/lib/types";
import { formatInr } from "@/lib/utils";
import { useEffect, useState } from "react";

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .orders()
      .then((data) => setOrders(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load orders."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageShell>
      <h1 className="text-3xl font-semibold tracking-tight">Orders</h1>
      <p className="mt-2 text-sm text-[var(--ink-muted)]">Sandbox orders for this demo browser session only.</p>
      {loading ? <Alert className="mt-6" title="Loading orders" /> : null}
      {error ? (
        <Alert tone="error" className="mt-6" title="Orders unavailable">
          {error}
        </Alert>
      ) : null}
      {!loading && !error && orders.length === 0 ? (
        <Alert className="mt-6" title="No orders yet">
          Checkout from a product page. Paid status appears only after a verified PayPal capture.
        </Alert>
      ) : null}
      <div className="mt-6 grid gap-3">
        {orders.map((order) => (
          <article key={order.id} className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-medium">{order.product.name}</h2>
                <p className="mt-1 text-sm text-[var(--ink-muted)]">
                  {formatInr(order.amount_inr)} · Sandbox {order.paypal_currency} {order.paypal_amount.toFixed(2)}
                </p>
              </div>
              <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-xs">{order.status}</span>
            </div>
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              PayPal order {order.paypal_order_id || "—"} · capture {order.paypal_capture_id || "not captured"}
            </p>
            <ButtonLink href={`/checkout/success?order_id=${order.id}`} variant="ghost" className="mt-2 text-xs">
              View status
            </ButtonLink>
          </article>
        ))}
      </div>
    </PageShell>
  );
}
