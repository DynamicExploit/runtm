import Link from 'next/link';

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-32">
      {/* Background gradient */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 left-1/2 h-[800px] w-[800px] -translate-x-1/2 rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div className="absolute top-0 right-0 h-[600px] w-[600px] rounded-full bg-indigo-500/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          {/* Badge */}
          <div className="animate-fade-in mb-8 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--background)] px-4 py-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--success)]" />
            <span className="text-sm text-[var(--muted)]">Fullstack Template</span>
          </div>

          {/* Headline */}
          <h1 className="animate-slide-up text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl">
            Build fullstack apps{' '}
            <span className="bg-gradient-to-r from-[var(--accent)] to-indigo-400 bg-clip-text text-transparent">
              faster
            </span>
          </h1>

          {/* Subheadline */}
          <p className="animation-delay-100 animate-slide-up mx-auto mt-6 max-w-xl text-lg text-[var(--muted)] md:text-xl">
            A production-ready template with Next.js frontend, FastAPI backend, and Zustand state
            management. Deploy with one command.
          </p>

          {/* Tech stack pills */}
          <div className="animation-delay-200 animate-slide-up mt-8 flex flex-wrap items-center justify-center gap-2">
            {['Next.js 14', 'FastAPI', 'TypeScript', 'Zustand', 'Tailwind'].map((tech) => (
              <span
                key={tech}
                className="rounded-full border border-[var(--border)] bg-[var(--card)] px-3 py-1 text-xs font-medium text-[var(--muted)]"
              >
                {tech}
              </span>
            ))}
          </div>

          {/* CTA Buttons */}
          <div className="animation-delay-300 animate-slide-up mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="#demo"
              className="w-full rounded-lg bg-[var(--accent)] px-8 py-3 font-medium text-white transition-all hover:bg-[var(--accent-dim)] hover:shadow-lg hover:shadow-[var(--accent)]/20 sm:w-auto"
            >
              Try the Demo
            </Link>
            <Link
              href="#features"
              className="w-full rounded-lg border border-[var(--border)] px-8 py-3 font-medium transition-colors hover:border-[var(--muted)] hover:bg-white/5 sm:w-auto"
            >
              Learn More
            </Link>
          </div>

          {/* Code block preview */}
          <div className="animation-delay-400 animate-slide-up mt-16 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
            <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-2">
              <div className="h-3 w-3 rounded-full bg-red-500/80" />
              <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
              <div className="h-3 w-3 rounded-full bg-green-500/80" />
              <span className="ml-2 text-xs text-[var(--muted)]">terminal</span>
            </div>
            <div className="p-4 text-left font-mono text-sm">
              <div className="flex items-center gap-2">
                <span className="text-[var(--muted)]">$</span>
                <span className="text-[var(--accent)]">runtm</span>
                <span>up</span>
              </div>
              <div className="mt-2 text-[var(--muted)]">
                <span className="text-[var(--success)]">✓</span> Frontend built
              </div>
              <div className="text-[var(--muted)]">
                <span className="text-[var(--success)]">✓</span> Backend deployed
              </div>
              <div className="text-[var(--muted)]">
                <span className="text-[var(--success)]">✓</span> Live at https://my-web-app.runtm.com
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

