import { ProductImage } from "@/components/product/ProductImage";
import { Button, ButtonLink } from "@/components/ui/button";
import type { RankedProduct } from "@/lib/types";
import { formatInr } from "@/lib/utils";

export function ProductCard({
  item,
  onCompare,
  onSelect,
  compared,
}: {
  item: RankedProduct;
  onCompare?: () => void;
  onSelect?: () => void;
  compared?: boolean;
}) {
  const product = item.product;
  const score = item.overall_score;
  const scorePercent =
    score != null ? Math.max(0, Math.min(100, Math.round(score * 100))) : null;

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--bg-elevated)] shadow-[var(--shadow)] transition-shadow duration-200 hover:shadow-md">
      <div className="relative">
        <ProductImage src={product.image_url} alt={product.name} />
        {item.rank != null ? (
          <span className="absolute left-3 top-3 rounded-full border border-white/70 bg-white/95 px-3 py-1 text-xs font-semibold text-stone-800 shadow-sm">
            #{item.rank} recommendation
          </span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-4 p-5">
        <div>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                {product.brand}
              </p>
              <h3 className="mt-1 text-base font-semibold leading-snug">
                {product.name}
              </h3>
            </div>
            <p className="shrink-0 text-base font-bold tabular-nums">
              {formatInr(product.price_inr)}
            </p>
          </div>

          <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
            {product.short_description}
          </p>
        </div>

        {scorePercent != null ? (
          <section
            className="rounded-xl border border-[var(--line)] bg-white/70 p-3"
            aria-label="Recommendation score"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-[var(--ink-muted)]">
                Weighted match score
              </span>
              <span className="text-sm font-bold tabular-nums">
                {score?.toFixed(2)?? "N/A"}
              </span>
            </div>
            <div
              className="mt-2 h-2 overflow-hidden rounded-full bg-stone-200"
              role="progressbar"
              aria-label="Weighted match score"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={scorePercent}
            >
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-[width]"
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-[var(--ink-muted)]">
              Relative ranking score, not a probability of satisfaction.
            </p>
          </section>
        ) : null}

        <SpecLine specs={product.specs} />

        {item.match_labels.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Why it matches
            </p>
            <div className="flex flex-wrap gap-1.5">
              {item.match_labels.map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <p className="text-sm leading-6">{item.explanation}</p>

        {item.advantages.length > 0 ? (
          <section>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Strengths
            </p>
            <ul className="space-y-1.5">
              {item.advantages.slice(0, 3).map((advantage) => (
                <li
                  key={advantage}
                  className="flex gap-2 text-sm leading-5"
                >
                  <span className="font-semibold text-emerald-700" aria-hidden="true">
                    +
                  </span>
                  <span>{advantage}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {item.disadvantages.length > 0 ? (
          <section>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Trade-offs
            </p>
            <ul className="space-y-1.5">
              {item.disadvantages.slice(0, 2).map((disadvantage) => (
                <li
                  key={disadvantage}
                  className="flex gap-2 text-sm leading-5 text-[var(--warn)]"
                >
                  <span aria-hidden="true">!</span>
                  <span>{disadvantage}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {item.missing_information.length > 0 ? (
          <details className="rounded-lg border border-[var(--line)] px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-[var(--ink-muted)]">
              Unknown specifications ({item.missing_information.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {item.missing_information.map((info) => (
                <li key={info} className="text-xs leading-5 text-[var(--ink-muted)]">
                  {info}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        <div className="mt-auto flex flex-wrap gap-2 border-t border-[var(--line)] pt-4">
          <ButtonLink
            href={`/products/${product.id}`}
            variant="secondary"
            className="text-xs"
          >
            View details
          </ButtonLink>

          {onCompare ? (
            <Button
              type="button"
              variant="ghost"
              className="text-xs"
              onClick={onCompare}
            >
              {compared ? "✓ In comparison" : "Compare"}
            </Button>
          ) : null}

          {onSelect ? (
            <Button type="button" className="text-xs" onClick={onSelect}>
              Buy with PayPal
            </Button>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function SpecLine({ specs }: { specs: Record<string, unknown> }) {
  const bits: string[] = [];

  if (typeof specs.ram_gb === "number") bits.push(`${specs.ram_gb} GB RAM`);
  if (typeof specs.storage_gb === "number") bits.push(`${specs.storage_gb} GB storage`);
  if (typeof specs.battery_hours === "number") bits.push(`${specs.battery_hours} h battery`);
  if (typeof specs.screen_inches === "number") bits.push(`${specs.screen_inches}" display`);
  if (typeof specs.connectivity === "string") bits.push(specs.connectivity);

  if (!bits.length) {
    return (
      <p className="text-xs text-[var(--ink-muted)]">
        See product details for specifications.
      </p>
    );
  }

  return (
    <p className="text-xs leading-5 text-[var(--ink-muted)]">
      {bits.join(" · ")}
    </p>
  );
}