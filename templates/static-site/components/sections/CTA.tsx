import Link from 'next/link';

export function CTA() {
  return (
    <section id="get-started" className="py-20 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <div className="relative overflow-hidden rounded-3xl border border-[var(--border)] bg-gradient-to-b from-[var(--accent)]/10 to-transparent p-8 md:p-16">
          {/* Background decoration */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -right-20 -top-20 h-[400px] w-[400px] rounded-full bg-[var(--accent)]/10 blur-3xl" />
            <div className="absolute -bottom-20 -left-20 h-[300px] w-[300px] rounded-full bg-purple-500/10 blur-3xl" />
          </div>

          <div className="relative mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Ready to get started?
            </h2>
            <p className="mt-4 text-lg text-[var(--muted)]">
              Deploy your landing page in minutes with a single command. No complex setup required.
            </p>

            {/* Code block */}
            <div className="mt-8 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--background)]">
              <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-2">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
                <span className="ml-2 text-xs text-[var(--muted)]">terminal</span>
              </div>
              <div className="p-4 text-left font-mono text-sm">
                <span className="text-[var(--muted)]">$</span>{' '}
                <span className="text-[var(--accent)]">runtm</span> up
              </div>
            </div>

            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="#"
                className="w-full rounded-lg bg-[var(--accent)] px-8 py-3 font-medium text-[var(--background)] transition-all hover:bg-[var(--accent-dim)] hover:shadow-lg hover:shadow-[var(--accent)]/20 sm:w-auto"
              >
                Start Building
              </Link>
              <Link
                href="#"
                className="w-full rounded-lg border border-[var(--border)] px-8 py-3 font-medium transition-colors hover:border-[var(--muted)] hover:bg-white/5 sm:w-auto"
              >
                View Documentation
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

