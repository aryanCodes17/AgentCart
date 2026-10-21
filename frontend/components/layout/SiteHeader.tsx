"use client";

import { Logo } from "@/components/brand/Logo";
import { ButtonLink } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useCart } from "@/lib/cart";
import { useState } from "react";

const links = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/shop", label: "Explore products" },
  { href: "/orders", label: "Orders" },
];

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const { cartCount } = useCart();
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-[var(--bg)]/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm text-[var(--ink-muted)] md:flex">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-[var(--ink)]">
              {link.label}
            </Link>
          ))}
          <Link href="/cart" className="hover:text-[var(--ink)]">
            Cart ({cartCount})
          </Link>
          <ButtonLink href="/shop">Start shopping</ButtonLink>
        </nav>
        <button
          type="button"
          className="rounded-md p-2 md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>
      
      {open ? (
        <div className="border-t border-[var(--line)] px-4 py-3 md:hidden">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="block py-2 text-sm"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}

          {/* Add the Cart link here, after links.map and before Start shopping */}
          <Link
            href="/cart"
            className="block py-2 text-sm"
            onClick={() => setOpen(false)}
          >
            Cart ({cartCount})
          </Link>

          <ButtonLink href="/shop" className="mt-2 w-full">
            Start shopping
          </ButtonLink>
        </div>
      ) : null}

    </header>
  );
}
