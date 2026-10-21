import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const tones = {
  info: "border-[var(--line)] bg-[var(--bg-elevated)] text-[var(--ink)]",
  error: "border-[#fecaca] bg-[#fef2f2] text-[var(--danger)]",
  success: "border-[#bbf7d0] bg-[#f0fdf4] text-[var(--ok)]",
  warn: "border-[#fde68a] bg-[#fffbeb] text-[var(--warn)]",
};

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: keyof typeof tones;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("rounded-[10px] border px-4 py-3 text-sm leading-6", tones[tone], className)}>
      {title ? <p className="font-medium">{title}</p> : null}
      {children ? <div className={title ? "mt-1" : undefined}>{children}</div> : null}
    </div>
  );
}
