import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function PageShell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full max-w-[1200px] flex-1 px-4 py-8 sm:px-6 sm:py-10", className)}>
      {children}
    </div>
  );
}
