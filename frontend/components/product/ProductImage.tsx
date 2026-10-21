"use client";

import { cn } from "@/lib/utils";
import { useState } from "react";

export function ProductImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={cn("relative overflow-hidden bg-[#ece7dc]", className)}>
      <div className="aspect-[4/3] w-full" />
      {failed ? (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-[var(--ink-muted)]">
          Image unavailable
        </div>
      ) : (
        // Native img avoids layout shift via the reserved aspect box; onError is a real fallback.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
