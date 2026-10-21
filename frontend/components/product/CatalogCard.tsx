  import { ProductImage } from "@/components/product/ProductImage";
  import { Button, ButtonLink } from "@/components/ui/button";
  import type { Product } from "@/lib/types";
  import { formatInr } from "@/lib/utils";

  export function CatalogCard({
    product,
    onCompare,
    onBuy,
    onAddToCart,
    compared,
  }: {
    product: Product;
    onCompare?: () => void;
    onBuy?: () => void;
    onAddToCart?: () => void;
    compared?: boolean;
  }) {
    return (
      <article className="flex flex-col overflow-hidden rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] shadow-[var(--shadow)]">
        <ProductImage src={product.image_url} alt={product.name} />
        <div className="flex flex-1 flex-col gap-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-[var(--ink-muted)]">{product.brand}</p>
              <h3 className="mt-1 text-base font-semibold leading-snug">{product.name}</h3>
            </div>
            <p className="shrink-0 text-sm font-medium">{formatInr(product.price_inr)}</p>
          </div>
          <p className="text-sm text-[var(--ink-muted)]">{product.short_description}</p>
          <p className="text-[11px] text-[var(--ink-muted)]">{product.data_label}</p>
          {!product.available ? (
            <p className="text-sm text-[var(--warn)]">Unavailable in the demo catalog.</p>
          ) : null}
          <div className="mt-auto flex flex-wrap gap-2 pt-2">
            <ButtonLink href={`/products/${product.id}`} variant="secondary" className="text-xs">
              View details
            </ButtonLink>
            {onCompare ? (
              <Button type="button" variant="ghost" className="text-xs" onClick={onCompare}>
                {compared ? "In comparison" : "Compare"}
              </Button>
            ) : null}         
            {onAddToCart ? (
              <Button
                type="button"
                variant="secondary"
                className="text-xs"
                onClick={onAddToCart}
                disabled={!product.available}
              >
                Add to Cart
              </Button>
            ) : null}
            {onBuy ? (
              <Button type="button" className="text-xs" onClick={onBuy} disabled={!product.available}>
                Buy with PayPal
              </Button>
            ) : null}
          </div>
        </div>
      </article>
    );
  }
