export type Product = {
  id: string;
  slug: string;
  name: string;
  brand: string;
  category: string;
  price_inr: number;
  currency: string;
  image_url: string;
  short_description: string;
  description: string;
  specs: Record<string, unknown>;
  available: boolean;
  data_source: string;
  data_label: string;
  detail_url: string | null;
};

export type ComponentScore = {
  name: string;
  score: number | null;
  reason: string;
  unknown: boolean;
};

export type RankedProduct = {
  product: Product;
  rank: number | null;
  eligible: boolean;
  exclusion_reason: string | null;
  overall_score: number | null;
  component_scores: ComponentScore[];
  advantages: string[];
  disadvantages: string[];
  missing_information: string[];
  match_labels: string[];
  explanation: string;
};

export type Requirement = {
  category: string | null;
  budget: { amount: number | null; currency: string };
  hard_constraints: Record<string, unknown>;
  preferences: Record<string, string>;
  use_cases: string[];
  excluded_brands: string[];
  preferred_brands: string[];
  query_text: string;
  weights: {
    price: number;
    performance: number;
    battery: number;
    display: number;
    portability: number;
  };
  needs_clarification: boolean;
  clarifying_question: string | null;
};

export type RankingResponse = {
  session_id: string | null;
  mode: "ai" | "rule_based";
  evaluated_count: number;
  eligible_count: number;
  excluded_count: number;
  weights: Record<string, number>;
  methodology: string;
  requirement: Requirement;
  eligible: RankedProduct[];
  excluded: RankedProduct[];
  tradeoff_summary: string;
  stages: string[];
};

export type Order = {
  id: string;
  product: Product;
  items: {
    product: Product;
    quantity: number;
    unit_price_inr: number;
  }[];
  status: string;
  amount_inr: number;
  currency: string;
  paypal_amount: number;
  paypal_currency: string;
  fx_rate_inr_per_usd: number;
  paypal_order_id: string | null;
  paypal_capture_id: string | null;
  paypal_status: string | null;
  approval_url: string | null;
  sandbox: boolean;
  created_at: string;
};

export type Health = {
  status: string;
  ai: { configured: boolean; provider: string; mode: string; model?: string | null };
  paypal: { configured: boolean; environment: string; charge_currency: string; catalog_currency: string };
  database: string;
  demo: boolean;
};

export type PublicSettings = {
  app_env: string;
  ai_provider: string;
  ai_configured: boolean;
  ai_mode: string;
  paypal_configured: boolean;
  paypal_environment: string;
  paypal_currency: string;
  catalog_currency: string;
  paypal_inr_per_usd: number;
  public_frontend_url: string;
  public_backend_url: string;
  database: string;
  demo: boolean;
};

