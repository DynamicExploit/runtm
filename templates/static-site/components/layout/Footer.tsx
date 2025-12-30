import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-[var(--border)] bg-[var(--background)]">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-8 md:grid-cols-4">
          {/* Brand */}
          <div className="md:col-span-2">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)]">
                <span className="font-mono text-sm font-bold text-[var(--background)]">R</span>
              </div>
              <span className="font-semibold tracking-tight">My Landing</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm text-[var(--muted)]">
              A beautiful landing page template built with Next.js and deployed on Runtm.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="mb-4 text-sm font-semibold">Product</h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="#features"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  Features
                </Link>
              </li>
              <li>
                <Link
                  href="#pricing"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  href="#"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  Documentation
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="mb-4 text-sm font-semibold">Company</h3>
            <ul className="space-y-2">
              <li>
                <Link
                  href="#about"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  About
                </Link>
              </li>
              <li>
                <Link
                  href="#"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  Blog
                </Link>
              </li>
              <li>
                <Link
                  href="#"
                  className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  Contact
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-[var(--border)] pt-8 md:flex-row">
          <p className="text-sm text-[var(--muted)]">
            © {new Date().getFullYear()} My Landing. All rights reserved.
          </p>
          <div className="flex gap-6">
            <Link
              href="#"
              className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
            >
              Privacy
            </Link>
            <Link
              href="#"
              className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
            >
              Terms
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

