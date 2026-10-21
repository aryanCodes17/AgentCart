"use client";

import { PageShell } from "@/components/layout/PageShell";
import { ProductImage } from "@/components/product/ProductImage";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getShopSessionId } from "@/lib/session";
import type { RankedProduct } from "@/lib/types";
import { formatInr } from "@/lib/utils";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function CompareInner() {
  const params = useSearchParams();
  const idsKey = params.get("ids") || "";
  const ids = idsKey.split(",").map((id) => id.trim()).filter(Boolean);
  const tooFew = ids.length < 2;
  const [items, setItems] = useState<RankedProduct[]>([]);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(
    tooFew ? "Select at least two products to compare." : null,
  );
  const [loading, setLoading] = useState(!tooFew);

  useEffect(() => {
    if (ids.length < 2) return;
    let cancelled = false;
    api
      .compare(ids.slice(0, 4), getShopSessionId())
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setSummary(data.tradeoff_summary);
        setError(data.missing_ids.length ? `Unknown ids: ${data.missing_ids.join(", ")}` : null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Compare failed.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [idsKey, ids]);

  return (
    <PageShell>
      <h1 className="text-3xl font-semibold tracking-tight">Compare</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ink-muted)]">
        Side-by-side catalog facts and constraint outcomes. If a shopping session exists, stored requirements are applied.
      </p>
      {loading ? <Alert className="mt-6" title="Comparing">Loading catalog rows.</Alert> : null}
      {error ? (
        <Alert tone="error" className="mt-6" title="Compare">
          {error}
        </Alert>
      ) : null}
      {summary ? <Alert className="mt-6">{summary}</Alert> : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <article key={item.product.id} className="overflow-hidden rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)]">
            <ProductImage src={item.product.image_url} alt={item.product.name} />
            <div className="space-y-3 p-4">
              <h2 className="font-semibold">{item.product.name}</h2>
              <p className="text-sm">{formatInr(item.product.price_inr)}</p>
              <p className="text-sm">{item.eligible ? "Eligible under current constraints" : item.exclusion_reason}</p>
              <p className="text-sm leading-6 text-[var(--ink-muted)]">{item.explanation}</p>
              <ul className="text-xs text-[var(--ink-muted)]">
                {item.component_scores.map((score) => (
                  <li key={score.name}>
                    {score.name}: {score.unknown ? "unknown" : score.score?.toFixed(2)} — {score.reason}
                  </li>
                ))}
              </ul>
              <ButtonLink href={`/products/${item.product.id}`} variant="secondary" className="text-xs">
                Details
              </ButtonLink>
            </div>
          </article>
        ))}
      </div>
    </PageShell>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<PageShell>Loading comparison…</PageShell>}>
      <CompareInner />
    </Suspense>
  );
}
