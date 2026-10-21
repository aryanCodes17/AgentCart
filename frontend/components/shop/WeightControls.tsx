"use client";

import { Button } from "@/components/ui/button";
import type { RankingResponse } from "@/lib/types";

const LABELS: Record<string, string> = {
  price: "Price fit",
  performance: "Performance",
  battery: "Battery",
  display: "Display",
  portability: "Portability",
};

export function WeightControls({
  weights,
  onChange,
  onApply,
  disabled,
}: {
  weights: RankingResponse["weights"];
  onChange: (next: RankingResponse["weights"]) => void;
  onApply: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
      <p className="text-sm font-medium">Ranking weights</p>
      <p className="mt-1 text-xs leading-5 text-[var(--ink-muted)]">
        Recalculated on the server from catalog attributes. This does not call an LLM.
      </p>
      <div className="mt-4 grid gap-3">
        {Object.entries(LABELS).map(([key, label]) => (
          <label key={key} className="grid gap-1 text-xs">
            <span className="flex justify-between">
              <span>{label}</span>
              <span className="text-[var(--ink-muted)]">{(weights[key] ?? 0).toFixed(2)}</span>
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weights[key] ?? 0}
              onChange={(event) => onChange({ ...weights, [key]: Number(event.target.value) })}
            />
          </label>
        ))}
      </div>
      <Button type="button" className="mt-4 w-full text-xs" onClick={onApply} disabled={disabled}>
        Recalculate ranking
      </Button>
    </div>
  );
}
