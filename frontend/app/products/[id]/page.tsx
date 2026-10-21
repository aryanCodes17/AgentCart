"use client";

import { BuyDialog } from "@/components/checkout/BuyDialog";
import { PageShell } from "@/components/layout/PageShell";
import { ProductImage } from "@/components/product/ProductImage";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Product } from "@/lib/types";
import { formatInr } from "@/lib/utils";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function ProductPage() {
  const params = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buy, setBuy] = useState(false);

  useEffect(() => {
    api
      .product(params.id)
      .then(setProduct)
      .catch((err) => setError(err instanceof Error ? err.message : "Product not found."));
  }, [params.id]);

  if (error) {
    return (
      <PageShell>
        <Alert tone="error" title="Product unavailable">
          {error}
        </Alert>
      </PageShell>
    );
  }

  if (!product) {
    return (
      <PageShell>
        <Alert title="Loading product">Fetching catalog details.</Alert>
      </PageShell>
    );
  }

  const specEntries = Object.entries(product.specs).filter(([, value]) => value !== null && value !== undefined);

  return (
    <PageShell>
      <div className="grid gap-8 lg:grid-cols-2">
        <ProductImage src={product.image_url} alt={product.name} className="rounded-[10px]" />
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--ink-muted)]">{product.brand}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">{product.name}</h1>
          <p className="mt-3 text-xl">{formatInr(product.price_inr)}</p>
          <p className="mt-4 text-sm leading-7 text-[var(--ink-muted)]">{product.description}</p>
          <p className="mt-3 text-xs text-[var(--ink-muted)]">
            {product.data_label} · {product.available ? "Listed as available" : "Listed as unavailable"}
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button type="button" onClick={() => setBuy(true)} disabled={!product.available}>
              Buy with PayPal
            </Button>
            <ButtonLink href={`/compare?ids=${product.id}`} variant="secondary">
              Add to compare
            </ButtonLink>
            <ButtonLink href="/shop" variant="ghost">
              Back to shop
            </ButtonLink>
          </div>
        </div>
      </div>
      <section className="mt-10">
        <h2 className="text-lg font-semibold">Specifications on file</h2>
        <p className="mt-1 text-sm text-[var(--ink-muted)]">
          Missing fields are omitted. Ranking never fills them with optimistic values.
        </p>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          {specEntries.map(([key, value]) => (
            <div key={key} className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] px-4 py-3">
              <dt className="text-xs uppercase tracking-wide text-[var(--ink-muted)]">{key}</dt>
              <dd className="mt-1 text-sm">{String(value)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <BuyDialog
        open={buy}
        productId={product.id}
        productName={product.name}
        priceInr={product.price_inr}
        onClose={() => setBuy(false)}
      />
    </PageShell>
  );
}
