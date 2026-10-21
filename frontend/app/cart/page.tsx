
"use client";

import { PageShell } from "@/components/layout/PageShell";
import { Button, ButtonLink } from "@/components/ui/button";
import { useCart } from "@/lib/cart";
import { formatInr } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  getShopSessionId,
  setShopSessionId,
  rememberCheckout,
} from "@/lib/session";
import { useState } from "react";

export default function CartPage() {
  const {
    items,
    removeFromCart,
    updateQuantity,
    clearCart,
    cartCount,
    cartTotal,
  } = useCart();
const [checkoutBusy, setCheckoutBusy] = useState(false);
const [checkoutError, setCheckoutError] = useState<string | null>(null);

async function handleCheckout() {
  setCheckoutBusy(true);
  setCheckoutError(null);

  try {
    let sessionId = getShopSessionId();

    if (!sessionId) {
      const created = await api.createSession();
      sessionId = created.id;
      setShopSessionId(sessionId);
    }

    const result = await api.createCartOrder(
      items.map(({ product, quantity }) => ({
        product_id: product.id,
        quantity,
      })),
      sessionId,
    );

    if (!result.approval_url) {
      throw new Error("PayPal did not return an approval URL.");
    }

    rememberCheckout({
      orderId: result.order.id,
      paypalOrderId: result.order.paypal_order_id || "",
      sessionId,
    });

    window.location.assign(result.approval_url);
  } catch (err) {
    setCheckoutError(
      err instanceof Error
        ? err.message
        : "Could not start PayPal checkout.",
    );
    setCheckoutBusy(false);
  }
}
  return (
    <PageShell>
      <section className="py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)]">
              Your selections
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">
              Shopping cart
            </h1>
            <p className="mt-2 text-sm text-[var(--ink-muted)]">
              {cartCount} {cartCount === 1 ? "item" : "items"} in your cart
            </p>
          </div>

          {items.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              onClick={clearCart}
            >
              Clear cart
            </Button>
          )}
        </div>

        {items.length === 0 ? (
          <div className="mt-8 rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-8 text-center">
            <h2 className="text-xl font-semibold">Your cart is empty</h2>
            <p className="mt-2 text-sm text-[var(--ink-muted)]">
              Explore the catalog and add products you like.
            </p>
            <div className="mt-5">
              <ButtonLink href="/shop">Explore products</ButtonLink>
            </div>
          </div>
        ) : (
          <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="space-y-4">
              {items.map(({ product, quantity }) => (
                <article
                  key={product.id}
                  className="flex flex-col gap-4 rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4 sm:flex-row sm:items-center"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs uppercase tracking-wide text-[var(--ink-muted)]">
                      {product.brand}
                    </p>
                    <h2 className="mt-1 font-semibold">{product.name}</h2>
                    <p className="mt-2 text-sm text-[var(--ink-muted)]">
                      {formatInr(product.price_inr)} each
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <label
                      htmlFor={`quantity-${product.id}`}
                      className="text-sm text-[var(--ink-muted)]"
                    >
                      Qty
                    </label>
                    <select
                      id={`quantity-${product.id}`}
                      value={quantity}
                      onChange={(event) =>
                        updateQuantity(
                          product.id,
                          Number(event.target.value),
                        )
                      }
                      className="rounded-md border border-[var(--line)] bg-[var(--bg)] px-3 py-2 text-sm"
                    >
                      {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((number) => (
                        <option key={number} value={number}>
                          {number}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center justify-between gap-4 sm:block sm:text-right">
                    <p className="font-semibold">
                      {formatInr(product.price_inr * quantity)}
                    </p>
                    <button
                      type="button"
                      onClick={() => removeFromCart(product.id)}
                      className="mt-1 text-sm text-[var(--warn)] hover:underline"
                    >
                      Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <aside className="h-fit rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-5">
              <h2 className="text-lg font-semibold">Order summary</h2>

              <div className="mt-5 flex justify-between gap-4 text-sm">
                <span className="text-[var(--ink-muted)]">Items</span>
                <span>{cartCount}</span>
              </div>

              <div className="mt-3 flex justify-between gap-4 text-sm">
                <span className="text-[var(--ink-muted)]">Subtotal</span>
                <span className="font-semibold">{formatInr(cartTotal)}</span>
              </div>

              <p className="mt-4 text-xs leading-5 text-[var(--ink-muted)]">
                Demo catalog pricing. Shipping and taxes are not included.
              </p>

              <ButtonLink href="/shop" variant="secondary" className="mt-5 w-full">
                Continue shopping
              </ButtonLink>

              {checkoutError && (
                <p className="mt-3 text-sm text-[var(--warn)]" role="alert">
                    {checkoutError}
                </p>
                )}

                <Button
                type="button"
                onClick={handleCheckout}
                disabled={checkoutBusy || items.length === 0}
                className="mt-4 w-full"
                >
                {checkoutBusy ? "Creating Sandbox order…" : "Checkout with PayPal"}
                </Button>

                <p className="mt-3 text-xs leading-5 text-[var(--ink-muted)]">
                PayPal Sandbox demo checkout. The server calculates the total from
                catalog prices. No live payment will be made.
                </p>
            </aside>
          </div>
        )}
      </section>
    </PageShell>
  );
}
