
"use client";

import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Order } from "@/lib/types";
import { formatInr } from "@/lib/utils";
import { useEffect, useState } from "react";
import {
  getShopSessionId,
  setShopSessionId,
  getOrCreateCheckoutKey,
  clearCheckoutKey,
  rememberCheckout,
} from "@/lib/session";
type Feedback = {
  kind: "success" | "info" | "error";
  message: string;
};

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconcilingId, setReconcilingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [retryingId, setRetryingId] = useState<string | null>(null);

  async function loadOrders() {
    const data = await api.orders();
    setOrders(data.items);
  }

  useEffect(() => {
    loadOrders()
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load orders."),
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleReconcile(orderId: string) {
    setReconcilingId(orderId);
    setFeedback((current) => {
      const next = { ...current };
      delete next[orderId];
      return next;
    });

    try {
      const result = await api.reconcileOrder(orderId);

      setOrders((current) =>
        current.map((order) =>
          order.id === orderId ? result.order : order,
        ),
      );

      if (result.reconciliation === "paid" ||
          result.reconciliation === "already_paid") {
        setFeedback((current) => ({
          ...current,
          [orderId]: {
            kind: "success",
            message: "Payment verified successfully. Order marked as paid.",
          },
        }));
      } else {
        setFeedback((current) => ({
          ...current,
          [orderId]: {
            kind: "info",
            message:
              result.message ||
              `Payment is not yet confirmed. PayPal status: ${result.paypal_status || "Unknown"}.`,
          },
        }));
      }
    } catch (err) {
      setFeedback((current) => ({
        ...current,
        [orderId]: {
          kind: "error",
          message:
            err instanceof Error
              ? err.message
              : "Payment verification failed. Try again later.",
        },
      }));
    } finally {
      setReconcilingId(null);
    }
  }

  async function handleRetryCheckout(order: Order) {
  setRetryingId(order.id);

  setFeedback((current) => {
    const next = { ...current };
    delete next[order.id];
    return next;
  });

  const sessionId = getShopSessionId() || (await api.createSession()).id;

  try {
    if (!getShopSessionId()) {
      setShopSessionId(sessionId);
    }

    if (!order.items?.length) {
      throw new Error(
        "Original cart items are unavailable. Cannot safely recreate checkout.",
      );
    }

    const checkoutItems = order.items.map((item) => ({
      product_id: item.product.id,
      quantity: item.quantity,
    }));

    const checkoutIntent = `retry:${order.id}:${sessionId}`;
    const idempotencyKey = getOrCreateCheckoutKey(checkoutIntent);

    const result = await api.createCartOrder(
      checkoutItems,
      sessionId,
      idempotencyKey,
    );

    if (!result.approval_url) {
      throw new Error("PayPal did not return an approval URL.");
    }

    rememberCheckout({
      orderId: result.order.id,
      paypalOrderId: result.order.paypal_order_id || "",
      sessionId,
    });

    clearCheckoutKey(checkoutIntent);
    window.location.assign(result.approval_url);
  } catch (err) {
    setFeedback((current) => ({
      ...current,
      [order.id]: {
        kind: "error",
        message:
          err instanceof Error
            ? err.message
            : "Could not restart checkout.",
      },
    }));
    setRetryingId(null);
  }
}

  return (
    <PageShell>
      <h1 className="text-3xl font-semibold tracking-tight">Orders</h1>
      <p className="mt-2 text-sm text-[var(--ink-muted)]">
        Sandbox orders for this demo browser session only.
      </p>

      {loading ? <Alert className="mt-6" title="Loading orders" /> : null}

      {error ? (
        <Alert tone="error" className="mt-6" title="Orders unavailable">
          {error}
        </Alert>
      ) : null}

      {!loading && !error && orders.length === 0 ? (
        <Alert className="mt-6" title="No orders yet">
          Checkout from a product page. Paid status appears only after a
          verified PayPal capture.
        </Alert>
      ) : null}

      <div className="mt-6 grid gap-3">
        {orders.map((order) => {
          const canReconcile =
            Boolean(order.paypal_order_id) &&
            ["pending", "approved_not_captured"].includes(order.status);

          const canRetryCheckout =
            order.status === "checkout_unavailable" &&
            Boolean(order.items?.length);

          const canContinueToPayPal =
            order.status === "pending_approval" &&
            Boolean(order.approval_url);

          const isReconciling = reconcilingId === order.id;
          const orderFeedback = feedback[order.id];

          return (
            <article
              key={order.id}
              className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-medium">{order.product.name}</h2>
                  <p className="mt-1 text-sm text-[var(--ink-muted)]">
                    {formatInr(order.amount_inr)} · Sandbox{" "}
                    {order.paypal_currency} {order.paypal_amount.toFixed(2)}
                  </p>
                </div>

                <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-xs">
                  {order.status.replaceAll("_", " ")}
                </span>
              </div>

              <p className="mt-2 text-xs text-[var(--ink-muted)]">
                PayPal order {order.paypal_order_id || "—"} · capture{" "}
                {order.paypal_capture_id || "not captured"}
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <ButtonLink
                  href={`/checkout/success?order_id=${order.id}`}
                  variant="ghost"
                  className="text-xs"
                >

                  {canRetryCheckout ? (
                    <button
                      type="button"
                      onClick={() => handleRetryCheckout(order)}
                      disabled={retryingId !== null}
                      className="rounded-md border border-[var(--line)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--bg)] disabled:opacity-50"
                    >
                      {retryingId === order.id ? "Creating new checkout..." : "Retry checkout"}
                    </button>
                  ) : null}
                </ButtonLink>
                {canContinueToPayPal ? (
                  <a
                    href={order.approval_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-md border border-[var(--line)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--bg)]"
                  >
                    Continue to PayPal
                  </a>
                ) : null}
                {canReconcile ? (
                  <button
                    type="button"
                    onClick={() => handleReconcile(order.id)}
                    disabled={reconcilingId !== null}
                    className="rounded-md border border-[var(--line)] px-3 py-2 text-xs font-medium transition hover:bg-[var(--bg)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isReconciling ? "Verifying..." : "Verify payment"}
                  </button>
                ) : null}
              </div>

              {orderFeedback ? (
                <div
                  role="status"
                  aria-live="polite"
                  className={`mt-3 rounded-md border p-3 text-sm ${
                    orderFeedback.kind === "success"
                      ? "border-emerald-500/30 bg-emerald-500/5"
                      : orderFeedback.kind === "error"
                        ? "border-red-500/30 bg-red-500/5"
                        : "border-[var(--line)] bg-[var(--bg)]"
                  }`}
                >
                  {orderFeedback.message}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </PageShell>
  );
}
