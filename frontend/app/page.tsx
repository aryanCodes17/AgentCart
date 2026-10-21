import { ButtonLink } from "@/components/ui/button";
import { EXAMPLES } from "@/lib/api";
import { useCart } from "@/lib/cart";
import Link from "next/link";

const STEPS = [
  {
    title: "Say what you need",
    body: "Budget, category, RAM, wireless, and other hard limits are extracted from your words — or you get one clarifying question.",
  },
  {
    title: "Search and filter the catalog",
    body: "Only demo inventory that survives hard constraints is ranked. Unknown specs are disclosed, not guessed.",
  },
  {
    title: "Compare on evidence",
    body: "Scores are a weighted average of catalog numbers. You can change weights and rerank without an LLM.",
  },
  {
    title: "PayPal Sandbox checkout",
    body: "The server prices the order from the catalog and captures payment only after PayPal confirms it. Redirects are not treated as payment.",
  },
];

export default function Home() {
  return (
    <main>
      <section className="border-b border-[var(--line)] bg-[var(--bg-elevated)]">
        <div className="mx-auto grid max-w-[1200px] gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:py-20">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)]">PayPal AI Hackathon prototype</p>
            <h1 className="mt-4 max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
              Your intent. Its intelligence. Your decision.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-[var(--ink-muted)]">
              AgentCart is a shopping agent for a labelled demo catalog. It enforces hard constraints in
              Python, explains recommendations from catalog fields, and uses genuine PayPal Sandbox APIs
              when credentials are configured.
            </p>
            <form action="/shop" className="mt-8 flex flex-col gap-3 sm:flex-row">
              <label className="sr-only" htmlFor="home-query">
                Shopping request
              </label>
              <input
                id="home-query"
                name="q"
                placeholder="Find a laptop for coding under ₹70,000 with 16 GB RAM"
                className="h-12 flex-1 rounded-[10px] border border-[var(--line)] bg-white px-4 text-sm outline-none focus:border-[var(--accent)]"
              />
              <button
                type="submit"
                className="h-12 rounded-[10px] bg-[var(--accent)] px-5 text-sm font-medium text-white"
              >
                Search
              </button>
            </form>
            <div className="mt-6 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <Link
                  key={example.label}
                  href={example.href}
                  className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs text-[var(--ink-muted)] hover:text-[var(--ink)]"
                >
                  {example.label}
                </Link>
              ))}
            </div>
          </div>
          <aside className="rounded-[10px] border border-[var(--line)] bg-[var(--bg)] p-6">
            <p className="text-sm font-medium">What this demo is — and is not</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-[var(--ink-muted)]">
              <li>Catalog prices and specs are internally consistent demo data, not live market quotes.</li>
              <li>Without a Gemini key, requirement extraction is labelled rule-based demo mode.</li>
              <li>Without PayPal Sandbox credentials, checkout returns a clear 503. Success is never faked.</li>
              <li>INR catalog amounts are charged in USD in Sandbox using a documented demo rate.</li>
            </ul>
            <div className="mt-6 flex gap-2">
              <ButtonLink href="/shop">Explore products</ButtonLink>
              <ButtonLink href="/orders" variant="secondary">
                Orders
              </ButtonLink>
            </div>
          </aside>
        </div>
      </section>
      <section id="how-it-works" className="mx-auto max-w-[1200px] px-4 py-16 sm:px-6">
        <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <div key={step.title} className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-5">
              <p className="text-xs text-[var(--ink-muted)]">0{index + 1}</p>
              <h3 className="mt-2 font-medium">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">{step.body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
