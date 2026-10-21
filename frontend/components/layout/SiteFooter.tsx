import { Logo } from "@/components/brand/Logo";
import Link from "next/link";

export function SiteFooter() {
  const github = process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/your-org/agentcart";
  return (
    <footer className="border-t border-[var(--line)] bg-[var(--bg-elevated)]">
      <div className="mx-auto grid max-w-[1200px] gap-8 px-4 py-12 sm:px-6 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo />
          <p className="mt-4 max-w-md text-sm leading-6 text-[var(--ink-muted)]">
            Your intent. Its intelligence. Your decision. AgentCart is a hackathon prototype.
            Catalog data is labelled demo inventory. PayPal transactions use Sandbox only.
          </p>
        </div>
        <div className="text-sm">
          <p className="font-medium">Product</p>
          <div className="mt-3 flex flex-col gap-2 text-[var(--ink-muted)]">
            <Link href="/shop">Shop</Link>
            <Link href="/orders">Orders</Link>
            <Link href="/settings">Settings</Link>
            <Link href="/compare">Compare</Link>
          </div>
        </div>
        <div className="text-sm">
          <p className="font-medium">Trust</p>
          <div className="mt-3 flex flex-col gap-2 text-[var(--ink-muted)]">
            <a href={github} target="_blank" rel="noreferrer">
              GitHub
            </a>
            <p>Privacy: this demo stores a local session id, not a customer identity.</p>
          </div>
        </div>
      </div>
      <div className="border-t border-[var(--line)] py-4 text-center text-xs text-[var(--ink-muted)]">
        Demo disclaimer — not a live store. No real money. No fabricated testimonials.
      </div>
    </footer>
  );
}
