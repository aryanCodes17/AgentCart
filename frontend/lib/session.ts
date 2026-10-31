const SHOP_SESSION_KEY = "agentcart_shop_session";
const LAST_ORDER_KEY = "agentcart_last_checkout";
const CHECKOUT_KEYS_KEY = "agentcart_checkout_keys";

export function getShopSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SHOP_SESSION_KEY);
}

export function setShopSessionId(id: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SHOP_SESSION_KEY, id);
}

export function rememberCheckout(payload: {
  orderId: string;
  paypalOrderId: string;
  sessionId: string;
}) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LAST_ORDER_KEY, JSON.stringify(payload));
}

export function lastCheckout(): {
  orderId: string;
  paypalOrderId: string;
  sessionId: string;
} | null {
  if (typeof window === "undefined") return null;

  const raw = window.localStorage.getItem(LAST_ORDER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as {
      orderId: string;
      paypalOrderId: string;
      sessionId: string;
    };
  } catch {
    return null;
  }
}

// Keep one stable key per checkout intent so retries reuse it.
export function getOrCreateCheckoutKey(intent: string): string {
  if (typeof window === "undefined") {
    throw new Error("Checkout keys are only available in the browser.");
  }

  const raw = window.localStorage.getItem(CHECKOUT_KEYS_KEY);
  let keys: Record<string, string> = {};

  try {
    keys = raw ? JSON.parse(raw) : {};
  } catch {
    keys = {};
  }

  if (keys[intent]) {
    return keys[intent];
  }

  const key = crypto.randomUUID();
  keys[intent] = key;

  window.localStorage.setItem(CHECKOUT_KEYS_KEY, JSON.stringify(keys));
  return key;
}

export function clearCheckoutKey(intent: string) {
  if (typeof window === "undefined") return;

  const raw = window.localStorage.getItem(CHECKOUT_KEYS_KEY);
  if (!raw) return;

  try {
    const keys = JSON.parse(raw) as Record<string, string>;
    delete keys[intent];
    window.localStorage.setItem(CHECKOUT_KEYS_KEY, JSON.stringify(keys));
  } catch {
    window.localStorage.removeItem(CHECKOUT_KEYS_KEY);
  }
}