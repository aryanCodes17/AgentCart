"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { Product } from "@/lib/types";

export type CartItem = {
  product: Product;
  quantity: number;
};

type CartContextValue = {
  items: CartItem[];
  addToCart: (product: Product) => void;
  removeFromCart: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearCart: () => void;
  cartCount: number;
  cartTotal: number;
};

const CartContext = createContext<CartContextValue | null>(null);
const STORAGE_KEY = "agentcart-cart";

function isCartItem(value: unknown): value is CartItem {
  if (!value || typeof value !== "object") return false;

  const item = value as Partial<CartItem>;
  const product = item.product;

  return (
    !!product &&
    typeof product === "object" &&
    typeof product.id === "string" &&
    typeof product.name === "string" &&
    typeof product.price_inr === "number" &&
    Number.isInteger(item.quantity) &&
    (item.quantity as number) >= 1
  );
}

function loadCart(): CartItem[] {
  if (typeof window === "undefined") return [];

  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === null) return [];

    const parsed: unknown = JSON.parse(saved);
    return Array.isArray(parsed) ? parsed.filter(isCartItem) : [];
  } catch (error) {
    console.error("Unable to restore AgentCart cart:", error);
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(loadCart);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      console.error("Unable to save AgentCart cart:", error);
    }
  }, [items]);

  const addToCart = useCallback((product: Product) => {
    if (!product.available) return;

    setItems((current) => {
      const existing = current.find(
        (item) => item.product.id === product.id,
      );

      if (existing) {
        return current.map((item) =>
          item.product.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }

      return [...current, { product, quantity: 1 }];
    });
  }, []);

  const removeFromCart = useCallback((productId: string) => {
    setItems((current) =>
      current.filter((item) => item.product.id !== productId),
    );
  }, []);

  const updateQuantity = useCallback(
    (productId: string, quantity: number) => {
      if (!Number.isInteger(quantity) || quantity < 1) return;

      setItems((current) =>
        current.map((item) =>
          item.product.id === productId
            ? { ...item, quantity }
            : item,
        ),
      );
    },
    [],
  );

  const clearCart = useCallback(() => setItems([]), []);

  const value: CartContextValue = {
    items,
    addToCart,
    removeFromCart,
    updateQuantity,
    clearCart,
    cartCount: items.reduce((sum, item) => sum + item.quantity, 0),
    cartTotal: items.reduce(
      (sum, item) => sum + item.product.price_inr * item.quantity,
      0,
    ),
  };

  return (
    <CartContext.Provider value={value}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);

  if (!context) {
    throw new Error("useCart must be used inside CartProvider.");
  }

  return context;
}