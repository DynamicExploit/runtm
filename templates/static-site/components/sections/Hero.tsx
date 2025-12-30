import Link from 'next/link';

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-32">
      {/* Background gradient */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 left-1/2 h-[800px] w-[800px] -translate-x-1/2 rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div className="absolute top-0 right-0 h-[600px] w-[600px] rounded-full bg-purple-500/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          {/* Badge */}
          <div className="animate-fade-in mb-8 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--background)] px-4 py-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />
            <span className="text-sm text-[var(--muted)]">Now available</span>
          </div>

          {/* Headline */}
          <h1 className="animate-slide-up text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl">
            Build something{' '}
            <span className="bg-gradient-to-r from-[var(--accent)] to-emerald-400 bg-clip-text text-transparent">
              amazing
            </span>
          </h1>

          {/* Subheadline */}
          <p className="animation-delay-100 animate-slide-up mx-auto mt-6 max-w-xl text-lg text-[var(--muted)] md:text-xl">
            A modern landing page template that&apos;s ready to deploy. Built with Next.js,
            TypeScript, and Tailwind CSS.
          </p>

          {/* CTA Buttons */}
          <div className="animation-delay-200 animate-slide-up mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="#get-started"
              className="w-full rounded-lg bg-[var(--accent)] px-8 py-3 font-medium text-[var(--background)] transition-all hover:bg-[var(--accent-dim)] hover:shadow-lg hover:shadow-[var(--accent)]/20 sm:w-auto"
            >
              Get Started
            </Link>
            <Link
              href="#features"
              className="w-full rounded-lg border border-[var(--border)] px-8 py-3 font-medium transition-colors hover:border-[var(--muted)] hover:bg-white/5 sm:w-auto"
            >
              Learn More
            </Link>
          </div>

          {/* Social proof */}
          <div className="animation-delay-300 animate-slide-up mt-16 flex flex-col items-center gap-4">
            <div className="flex -space-x-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-[var(--background)] bg-gradient-to-br from-[var(--accent)]/20 to-purple-500/20"
                >
                  <span className="text-xs font-medium">{i}</span>
                </div>
              ))}
            </div>
            <p className="text-sm text-[var(--muted)]">
              Trusted by <span className="text-[var(--foreground)]">1,000+</span> developers
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

