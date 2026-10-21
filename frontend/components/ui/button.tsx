import { cn } from "@/lib/utils";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

const styles = {
  primary:
    "bg-[var(--accent)] text-white hover:bg-[#1e40af] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]",
  secondary:
    "bg-white text-[var(--ink)] border border-[var(--line)] hover:bg-[#f3efe6]",
  ghost: "bg-transparent text-[var(--ink)] hover:bg-black/5",
  danger: "bg-[var(--danger)] text-white hover:bg-[#991b1b]",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof styles }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function ButtonLink({
  href,
  children,
  variant = "primary",
  className,
}: {
  href: string;
  children: ReactNode;
  variant?: keyof typeof styles;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-medium transition-colors",
        styles[variant],
        className,
      )}
    >
      {children}
    </Link>
  );
}
