"use client";

import { BuyDialog } from "@/components/checkout/BuyDialog";
import { PageShell } from "@/components/layout/PageShell";
import { CatalogCard } from "@/components/product/CatalogCard";
import { ProductCard } from "@/components/product/ProductCard";
import { RequirementSummary } from "@/components/shop/RequirementSummary";
import { WeightControls } from "@/components/shop/WeightControls";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EXAMPLES, api } from "@/lib/api";
import { setShopSessionId } from "@/lib/session";
import type { Health, Product, RankingResponse } from "@/lib/types";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useCart } from "@/lib/cart";

const CATEGORIES = [
  { id: "all", label: "All Items" },
  { id: "laptop", label: "Laptops" },
  { id: "headphones", label: "Headphones" },
  { id: "monitor", label: "Monitors" },
  { id: "keyboard", label: "Keyboards" },
  { id: "mouse", label: "Mice" },
  { id: "smartphone", label: "Phones" },
  { id: "tablet", label: "Tablets" },
];

function ShopInner() {
  const params = useSearchParams();
  const router = useRouter();
  const initialQ = params.get("q") || "";
  const [query, setQuery] = useState(initialQ);
  const [followUp, setFollowUp] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [ranking, setRanking] = useState<RankingResponse | null>(null);
  const [weights, setWeights] = useState<RankingResponse["weights"]>({
    price: 0.25,
    performance: 0.25,
    battery: 0.2,
    display: 0.15,
    portability: 0.15,
  });
  const [loading, setLoading] = useState(Boolean(initialQ));
  const [error, setError] = useState<string | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const { addToCart } = useCart();
  const [buy, setBuy] = useState<{ id: string; name: string; price: number } | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const searchedQueryRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelectCategory(category: string) {
    setSelectedCategory(category);
    setCatalogLoading(true);
  }

  useEffect(() => {
    let cancelled = false;
    const filterParams: Record<string, string> = { limit: "50" };
    if (selectedCategory !== "all") {
      filterParams.category = selectedCategory;
    }

    api
      .products(filterParams)
      .then((data) => {
        if (!cancelled) {
          setCatalog(data.items);
          setCatalogLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Catalog unavailable.");
          setCatalogLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCategory]);

  async function runSearch(message: string) {
    if (!message.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.search(message, sessionIdRef.current);
      setRanking(result);
      setWeights(result.weights);
      if (result.session_id) {
        sessionIdRef.current = result.session_id;
        setShopSessionId(result.session_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!initialQ || searchedQueryRef.current === initialQ) return;
    searchedQueryRef.current = initialQ;
    void runSearch(initialQ);
  }, [initialQ]);

  function toggleCompare(id: string) {
    setCompareIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= 4) return current;
      return [...current, id];
    });
  }

  function clearSearch() {
    setRanking(null);
    setQuery("");
    searchedQueryRef.current = null;
    router.replace("/shop");
  }

  const modeLabel = useMemo(() => {
    if (!health) return "Checking providers…";
    const ai = health.ai.configured ? `AI (${health.ai.provider})` : "Rule-based demo mode";
    const pay = health.paypal.configured ? "PayPal Sandbox configured" : "PayPal credentials not configured";
    return `${ai} · ${pay}`;
  }, [health]);

  return (
    <PageShell>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Shop</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ink-muted)]">
            Browse the demo catalog or ask in natural language. Hard constraints are enforced on the server.
          </p>
        </div>
        <p className="text-xs text-[var(--ink-muted)]">{modeLabel}</p>
      </div>

      <form
        className="mt-6 flex flex-col gap-3 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          router.replace(`/shop?q=${encodeURIComponent(query)}`);
          searchedQueryRef.current = query;
          void runSearch(query);
        }}
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find wireless headphones under ₹8,000 with good battery life"
          className="h-12 flex-1 rounded-[10px] border border-[var(--line)] bg-white px-4 text-sm outline-none focus:border-[var(--accent)]"
        />
        <Button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Ask AgentCart"}
        </Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.filter((item) => item.href.startsWith("/shop")).map((example) => (
          <button
            key={example.label}
            type="button"
            className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)]"
            onClick={() => {
              const value = decodeURIComponent(example.href.split("q=")[1] || "");
              setQuery(value);
              searchedQueryRef.current = value;
              router.replace(example.href);
              void runSearch(value);
            }}
          >
            {example.label}
          </button>
        ))}
      </div>

      {error ? (
        <Alert tone="error" title="Request failed" className="mt-6">
          {error}
        </Alert>
      ) : null}

      {loading ? (
        <Alert className="mt-6" title="Working">
          Understanding your requirements, searching the catalog, and applying hard constraints.
        </Alert>
      ) : null}

      {ranking ? (
        <div className="mt-8">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-4">
            <p className="text-sm text-[var(--ink-muted)]">
              Showing recommendations for <span className="font-semibold text-[var(--ink)]">&ldquo;{ranking.requirement.query_text || query}&rdquo;</span>
            </p>

            <button
              type="button"
              onClick={clearSearch}
              className="rounded-[8px] border border-[var(--line)] bg-[var(--bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] hover:bg-white"
            >
              Clear search & Browse catalog
            </button>
          </div>
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
            <aside className="space-y-4">
              <RequirementSummary requirement={ranking.requirement} />
              <WeightControls
                weights={weights}
                onChange={setWeights}
                disabled={loading || !ranking.session_id}
                onApply={async () => {
                  if (!ranking.session_id) return;
                  setLoading(true);
                  setError(null);
                  try {
                    const result = await api.rerank(ranking.session_id, weights);
                    setRanking(result);
                    setWeights(result.weights);
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Rerank failed.");
                  } finally {
                    setLoading(false);
                  }
                }}
              />
              <form
                className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (!ranking.session_id || !followUp.trim()) return;
                  setLoading(true);
                  setError(null);
                  try {
                    const result = await api.followUp(ranking.session_id, followUp);
                    setRanking(result);
                    setWeights(result.weights);
                    setFollowUp("");
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Follow-up failed.");
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                <label className="text-sm font-medium" htmlFor="follow-up">
                  Follow up
                </label>
                <textarea
                  id="follow-up"
                  value={followUp}
                  onChange={(event) => setFollowUp(event.target.value)}
                  rows={3}
                  className="mt-2 w-full rounded-[10px] border border-[var(--line)] bg-white p-2 text-sm"
                  placeholder="Raise battery importance, or exclude a brand"
                />
                <Button type="submit" className="mt-3 w-full text-xs" disabled={loading}>
                  Update requirements
                </Button>
              </form>
            </aside>
            <div>
              <Alert tone={ranking.mode === "ai" ? "info" : "warn"} title={ranking.mode === "ai" ? "AI extraction" : "Rule-based demo mode"}>
                {ranking.tradeoff_summary}
              </Alert>
              <p className="mt-4 text-sm text-[var(--ink-muted)]">
                {ranking.eligible_count} eligible · {ranking.excluded_count} excluded · {ranking.evaluated_count} evaluated
              </p>
              {ranking.eligible.length === 0 ? (
                <Alert className="mt-4" title="No products meet the hard constraints">
                  Review excluded items below. Missing required specifications cause exclusion, not a guessed pass.
                </Alert>
              ) : (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {ranking.eligible.map((item) => (
                    <ProductCard
                      key={item.product.id}
                      item={item}
                      compared={compareIds.includes(item.product.id)}
                      onCompare={() => toggleCompare(item.product.id)}
                      onSelect={() =>
                        setBuy({ id: item.product.id, name: item.product.name, price: item.product.price_inr })
                      }
                    />
                  ))}
                </div>
              )}
              {ranking.excluded.length ? (
                <details className="mt-8 rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
                  <summary className="cursor-pointer text-sm font-medium">
                    Excluded products ({ranking.excluded.length})
                  </summary>
                  <ul className="mt-3 space-y-3 text-sm">
                    {ranking.excluded.map((item) => (
                      <li key={item.product.id}>
                        <span className="font-medium">{item.product.name}</span>
                        <span className="text-[var(--ink-muted)]"> — {item.exclusion_reason}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Demo inventory</h2>
              <p className="mt-1 text-sm text-[var(--ink-muted)]">Labelled catalog data. Filter by category or search with natural language.</p>
            </div>
            <p className="text-xs text-[var(--ink-muted)]">{catalog.length} items</p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {CATEGORIES.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => handleSelectCategory(category.id)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                  selectedCategory === category.id
                    ? "bg-[var(--accent)] text-white"
                    : "border border-[var(--line)] bg-[var(--bg-elevated)] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                }`}
              >
                {category.label}
              </button>
            ))}
          </div>

          {catalogLoading ? (
            <Alert className="mt-6" title="Loading catalog">
              Fetching products from the API.
            </Alert>
          ) : catalog.length === 0 && !error ? (
            <Alert className="mt-6" title="No products found in category">
              Try selecting another category or clear filters.
            </Alert>
          ) : (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {catalog.map((product) => (
                <CatalogCard
                  key={product.id}
                  product={product}
                  compared={compareIds.includes(product.id)}
                  onCompare={() => toggleCompare(product.id)}
                  onAddToCart={() => addToCart(product)}
                  onBuy={() => setBuy({ id: product.id, name: product.name, price: product.price_inr })}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {compareIds.length >= 2 ? (
        <div className="sticky bottom-4 mt-8 flex justify-center">
          <Button type="button" onClick={() => router.push(`/compare?ids=${compareIds.join(",")}`)}>
            Compare {compareIds.length} products
          </Button>
        </div>
      ) : null}

      <BuyDialog
        open={Boolean(buy)}
        productId={buy?.id || ""}
        productName={buy?.name || ""}
        priceInr={buy?.price || 0}
        onClose={() => setBuy(null)}
      />
    </PageShell>
  );
}

export default function ShopPage() {
  return (
    <Suspense fallback={<PageShell>Loading shop…</PageShell>}>
      <ShopInner />
    </Suspense>
  );
}
