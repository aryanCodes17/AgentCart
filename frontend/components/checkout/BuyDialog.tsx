"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  rememberCheckout,
  setShopSessionId,
  getShopSessionId,
  getOrCreateCheckoutKey,
  clearCheckoutKey,
} from "@/lib/session";
import { formatInr } from "@/lib/utils";
import { useState } from "react";

export function BuyDialog({
  productId,
  productName,
  priceInr,
  open,
  onClose,
}: {
  productId: string;
  productName: string;
  priceInr: number;
  open: boolean;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function confirm() {
  setBusy(true);
  setError(null);

  let checkoutIntent: string | null = null;

  try {
    let sessionId = getShopSessionId();

    if (!sessionId) {
      const created = await api.createSession();
      sessionId = created.id;
      setShopSessionId(sessionId);
    }

    checkoutIntent = `product:${sessionId}:${productId}`;
    const idempotencyKey = getOrCreateCheckoutKey(checkoutIntent);

    const result = await api.createOrder(
      productId,
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
    setError(
      err instanceof Error
        ? err.message
        : "Could not start PayPal checkout.",
    );
    setBusy(false);
  }
}

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-5 shadow-lg">
        <h2 className="text-lg font-semibold">Confirm PayPal Sandbox checkout</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
          {productName} is listed at {formatInr(priceInr)} in the demo catalog. The server will convert that
          amount to USD with the documented demo rate and create a Sandbox order. This is not a live charge.
        </p>
        {error ? (
          <Alert tone="error" title="Checkout did not start" className="mt-4">
            {error}
          </Alert>
        ) : null}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" onClick={confirm} disabled={busy}>
            {busy ? "Creating Sandbox order…" : "Continue to PayPal"}
          </Button>
        </div>
      </div>
    </div>
  );
}
