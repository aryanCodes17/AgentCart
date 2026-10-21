import type { Requirement } from "@/lib/types";
import { formatInr } from "@/lib/utils";

export function RequirementSummary({ requirement }: { requirement: Requirement }) {
  const items = [
    requirement.category ? `Category: ${requirement.category}` : null,
    requirement.budget.amount != null ? `Budget: ${formatInr(requirement.budget.amount)}` : "Budget: not specified",
    requirement.hard_constraints.minimum_ram_gb
      ? `Min RAM: ${requirement.hard_constraints.minimum_ram_gb} GB`
      : null,
    requirement.use_cases.length ? `Use: ${requirement.use_cases.join(", ")}` : null,
    requirement.excluded_brands.length ? `Excluded: ${requirement.excluded_brands.join(", ")}` : null,
  ].filter(Boolean);

  return (
    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
      <p className="text-sm font-medium">Extracted requirements</p>
      <ul className="mt-2 space-y-1 text-sm text-[var(--ink-muted)]">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {requirement.needs_clarification && requirement.clarifying_question ? (
        <p className="mt-3 text-sm">{requirement.clarifying_question}</p>
      ) : null}
    </div>
  );
}
