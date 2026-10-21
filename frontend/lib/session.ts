const SHOP_SESSION_KEY = "agentcart_shop_session";
const LAST_ORDER_KEY = "agentcart_last_checkout";

export function getShopSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SHOP_SESSION_KEY);
}

export function setShopSessionId(id: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SHOP_SESSION_KEY, id);
}

export function rememberCheckout(payload: { orderId: string; paypalOrderId: string; sessionId: string }) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LAST_ORDER_KEY, JSON.stringify(payload));
}

export function lastCheckout(): { orderId: string; paypalOrderId: string; sessionId: string } | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(LAST_ORDER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as { orderId: string; paypalOrderId: string; sessionId: string };
  } catch {
    return null;
  }
}
