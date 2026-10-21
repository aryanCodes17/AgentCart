"use client";

import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/ui/alert";
import { api } from "@/lib/api";
import type { Health, PublicSettings } from "@/lib/types";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.health(), api.settings()]).then(([healthRes, settingsRes]) => {
      if (cancelled) return;
      if (healthRes.status === "fulfilled") {
        setHealth(healthRes.value);
      }
      if (settingsRes.status === "fulfilled") {
        setSettings(settingsRes.value);
      }
      if (healthRes.status === "rejected" && settingsRes.status === "rejected") {
        const reason = healthRes.reason;
        setError(reason instanceof Error ? reason.message : "Backend unreachable.");
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PageShell className="max-w-2xl">
      <h1 className="text-3xl font-semibold tracking-tight">Settings & System Status</h1>
      <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
        Public flags and parameters only. Secrets stay on the server. Copy values from <code>.env.example</code> into a local{" "}
        <code>.env</code> file — never commit credentials.
      </p>
      {error ? (
        <Alert tone="error" className="mt-6" title="Cannot reach API">
          {error} Start the FastAPI server on port 8000 and set NEXT_PUBLIC_API_URL if needed.
        </Alert>
      ) : null}
      {!health && !settings && !error ? <Alert className="mt-6" title="Loading configuration" /> : null}
      {health || settings ? (
        <dl className="mt-6 grid gap-3">
          <Row label="API Status" value={health?.status ?? "ok"} />
          <Row label="Environment" value={settings?.app_env ?? "development"} />
          <Row label="Database Engine" value={settings?.database ?? health?.database ?? "sqlite"} />
          <Row
            label="AI Provider"
            value={
              settings?.ai_configured ?? health?.ai.configured
                ? `${settings?.ai_provider ?? health?.ai.provider ?? "gemini"} (Active)`
                : "Rule-based fallback"
            }
          />
          <Row label="AI Mode" value={settings?.ai_mode ?? health?.ai.mode ?? "rule_based"} />
          <Row
            label="PayPal Sandbox"
            value={
              settings?.paypal_configured ?? health?.paypal.configured
                ? "Configured (Ready)"
                : "Credentials not set (HTTP 503 demo refusal)"
            }
          />
          <Row label="PayPal Environment" value={settings?.paypal_environment ?? health?.paypal.environment ?? "sandbox"} />
          <Row label="Catalog Currency" value={settings?.catalog_currency ?? "INR"} />
          <Row label="PayPal Charge Currency" value={settings?.paypal_currency ?? health?.paypal.charge_currency ?? "USD"} />
          {settings?.paypal_inr_per_usd ? (
            <Row label="Demo FX Rate" value={`${settings.paypal_inr_per_usd} INR/USD (Documented fixed rate)`} />
          ) : null}
          {settings?.public_frontend_url ? (
            <Row label="Public Frontend URL" value={settings.public_frontend_url} />
          ) : null}
          {settings?.public_backend_url ? (
            <Row label="Public Backend URL" value={settings.public_backend_url} />
          ) : null}
        </dl>
      ) : null}
    </PageShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-[10px] border border-[var(--line)] bg-[var(--bg-elevated)] px-4 py-3 text-sm">
      <dt className="text-[var(--ink-muted)]">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
