'use client';

import { useState } from 'react';
import Link from 'next/link';

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="fixed left-0 right-0 top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-lg">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)]">
            <span className="font-mono text-sm font-bold text-[var(--background)]">R</span>
          </div>
          <span className="font-semibold tracking-tight">My Landing</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-8 md:flex">
          <Link
            href="#features"
            className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          >
            Features
          </Link>
          <Link
            href="#pricing"
            className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          >
            Pricing
          </Link>
          <Link
            href="#about"
            className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          >
            About
          </Link>
        </div>

        {/* CTA Button */}
        <div className="hidden md:block">
          <Link
            href="#get-started"
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--background)] transition-colors hover:bg-[var(--accent-dim)]"
          >
            Get Started
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          className="md:hidden"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle menu"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
              />
            )}
          </svg>
        </button>
      </nav>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="border-t border-[var(--border)] bg-[var(--background)] px-6 py-4 md:hidden">
          <div className="flex flex-col gap-4">
            <Link
              href="#features"
              className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              onClick={() => setMobileMenuOpen(false)}
            >
              Features
            </Link>
            <Link
              href="#pricing"
              className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              onClick={() => setMobileMenuOpen(false)}
            >
              Pricing
            </Link>
            <Link
              href="#about"
              className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              onClick={() => setMobileMenuOpen(false)}
            >
              About
            </Link>
            <Link
              href="#get-started"
              className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-center text-sm font-medium text-[var(--background)] transition-colors hover:bg-[var(--accent-dim)]"
              onClick={() => setMobileMenuOpen(false)}
            >
              Get Started
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

