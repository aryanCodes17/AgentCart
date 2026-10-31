"use client";

import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getShopSessionId, lastCheckout } from "@/lib/session";
import type { Order } from "@/lib/types";
import { formatInr } from "@/lib/utils";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function CheckoutInner() {
  const params = useSearchParams();
  const orderId = params.get("order_id");
  const cancelled = params.get("cancelled") === "1";
  const token = params.get("token");
  const [order, setOrder] = useState<Order | null>(null);
  const [status, setStatus] = useState<"pending" | "paid" | "cancelled" | "error">("pending");
  const [message, setMessage] = useState("Checking PayPal and server records…");

  useEffect(() => {
    const remembered = lastCheckout();
    const sessionId = remembered?.sessionId || getShopSessionId();
    const paypalOrderId = token || remembered?.paypalOrderId;

    async function run() {
      try {
        if (!orderId) {
          setStatus("error");
          setMessage("Missing order_id. A redirect is not treated as payment.");
          return;
        }
        const fetched = await api.order(orderId);
        setOrder(fetched.order);

        if (cancelled) {
          const cancelPaypalId = fetched.order.paypal_order_id || paypalOrderId;
          if (cancelPaypalId && sessionId) {
            const cancelledOrder = await api.cancelOrder(cancelPaypalId, sessionId);
            setOrder(cancelledOrder.order);
          }
          setStatus("cancelled");
          setMessage("Checkout was cancelled. No capture was attempted.");
          return;
        }


        if (fetched.order.status === "paid" && fetched.order.paypal_capture_id) {
          setStatus("paid");
          setMessage("Payment captured. Status comes from PayPal, not from this page load.");
          return;
        }

        // Opening an order-status page must never initiate payment capture.
      if (!token) {
        setStatus("pending");
        setMessage(
          "Payment has not been verified on this page. Return from PayPal to complete payment verification.",
        );
        return;
      }

      // Ensure the PayPal return token belongs to this local order.
      if (fetched.order.paypal_order_id !== token) {
        setStatus("error");
        setMessage(
          "The PayPal return token does not match this order. Payment was not captured.",
        );
        return;
      }

      if (!sessionId) {
        setStatus("error");
        setMessage(
          "The shopping session is unavailable. Payment verification cannot continue.",
        );
        return;
      }

      const captured = await api.captureOrder(token, sessionId);
      setOrder(captured.order);

      if (
        captured.order.status === "paid" &&
        captured.order.paypal_capture_id
      ) {
        setStatus("paid");
        setMessage(
          captured.duplicate
            ? "Payment was already captured and verified."
            : "PayPal capture completed successfully.",
        );
      } else {
        setStatus("error");
        setMessage(
          `Capture did not complete. Server status: ${captured.order.status}.`,
        );
      }
        setOrder(captured.order);
        if (captured.order.status === "paid" && captured.order.paypal_capture_id) {
          setStatus("paid");
          setMessage(captured.duplicate ? "Already captured." : "PayPal capture completed.");
        } else {
          setStatus("error");
          setMessage(`Capture did not complete. Server status: ${captured.order.status}.`);
        }
      } catch (err) {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Could not verify payment.");
      }
    }

    void run();
  }, [orderId, cancelled, token]);

  const tone = status === "paid" ? "success" : status === "cancelled" ? "warn" : status === "error" ? "error" : "info";

  return (
    <PageShell className="max-w-2xl">
      <h1 className="text-3xl font-semibold tracking-tight">Checkout</h1>
      <Alert tone={tone} title={status === "pending" ? "Pending" : status} className="mt-6">
        {message}
      </Alert>
      {order ? (
        <div className="mt-6 rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-5 text-sm leading-6">
          <p className="font-medium">{order.product.name}</p>
          <p className="text-[var(--ink-muted)]">
            Catalog {formatInr(order.amount_inr)} · Sandbox {order.paypal_currency} {order.paypal_amount.toFixed(2)} at{" "}
            {order.fx_rate_inr_per_usd} INR/USD (documented demo rate, not a live FX quote).
          </p>
          <p className="mt-2 text-xs text-[var(--ink-muted)]">
            Internal status: {order.status}. PayPal status: {order.paypal_status || "—"}. Capture id:{" "}
            {order.paypal_capture_id || "none"}.
          </p>
        </div>
      ) : null}
      <div className="mt-6 flex gap-2">
        <ButtonLink href="/orders" variant="secondary">
          Orders
        </ButtonLink>
        <ButtonLink href="/shop" variant="ghost">
          Continue shopping
        </ButtonLink>
      </div>
    </PageShell>
  );
}

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={<PageShell>Loading checkout status…</PageShell>}>
      <CheckoutInner />
    </Suspense>
  );
}
