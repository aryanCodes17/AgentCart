import Link from "next/link";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="inline-flex items-center gap-2.5 text-inherit no-underline">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <rect x="1" y="1" width="26" height="26" rx="6" fill="#172554" />
        <path d="M8 18.5V9.5h3.2c2.4 0 3.9 1.2 3.9 3.2 0 2.1-1.5 3.3-3.9 3.3H11v2.5H8zm3.1-4.7h.4c.9 0 1.5-.5 1.5-1.2s-.6-1.2-1.5-1.2h-.4v2.4z" fill="#FBF9F4" />
        <circle cx="20.2" cy="18.2" r="2.1" fill="#1D4ED8" />
      </svg>
      {compact ? null : (
        <span className="flex flex-col leading-none">
          <span className="text-[15px] font-semibold tracking-tight">AgentCart</span>
          <span className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-[var(--ink-muted)]">
            Agentic commerce
          </span>
        </span>
      )}
    </Link>
  );
}
