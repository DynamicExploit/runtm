# Static Site - Claude Instructions

This is a static Next.js site deployed on Runtm.

## Contract Rules

| File | Editable? | How to Change |
|------|-----------|---------------|
| `runtm.yaml` | NO | Use `runtm apply` or CLI commands |
| `Dockerfile` | YES | Edit freely, but must expose declared port |
| Health endpoint | YES | Must return 200 at manifest's `health_path` |
| Lockfiles | AUTO | Managed by `runtm run`/`runtm deploy` |

### Invariants (enforced at deploy)
- Port must match `runtm.yaml` (3000)
- `health_path` must return 200
- Lockfile must be in sync

## What is a Static Site?

Fast, zero-backend pages served as files.

**Use cases:**
- Marketing website
- Product landing page/waitlist
- Docs/changelog
- Status/press page

## Critical Rules

1. **Port 3000** - Must be served on port 3000
2. **Static Export** - Uses `output: 'export'`, no server code
3. **Health Check** - `/health` served from `public/health` (DO NOT DELETE)
4. **Lightweight** - Avoid heavy dependencies

## Project Structure

```
app/                         # Next.js pages
components/
├── layout/                  # Header, Footer
├── pages/                   # Page-specific components
│   └── home/                # Home page components
│       ├── HomeHero.tsx
│       ├── HomeFeatures.tsx
│       └── HomeCTA.tsx
└── ui/                      # Reusable UI components
public/
├── health                   # Health check (DO NOT DELETE)
└── images/
```

## Component Organization

### Page-Specific (`components/pages/`)
Components tied to a specific page's business logic:
```
pages/home/HomeHero.tsx      # Hero for home page only
pages/about/AboutTeam.tsx    # Team section for about page only
```

### Reusable UI (`components/ui/`)
Generic, reusable components:
```
ui/Button.tsx                # Used across multiple pages
ui/Card.tsx                  # Generic card component
```

## Adding Pages

### 1. Create page components

```
components/pages/pricing/
├── index.ts
├── PricingHero.tsx
└── PricingPlans.tsx
```

### 2. Create the page

```tsx
// app/pricing/page.tsx
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { PricingHero, PricingPlans } from '@/components/pages/pricing';

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <PricingHero />
        <PricingPlans />
      </main>
      <Footer />
    </div>
  );
}
```

## Styling

CSS variables in `app/globals.css`:
- `--background`, `--foreground`, `--accent`, `--muted`, `--border`

## Environment Variables (Optional)

Static sites typically don't need secrets, but you can use env vars for optional features like analytics:

```yaml
# runtm.yaml (optional)
env_schema:
  - name: ANALYTICS_ID
    type: string
    required: false
    description: "Analytics tracking ID"
```

```bash
runtm secrets set ANALYTICS_ID=UA-xxx   # Stores in .env.local
```

**Note:** Env vars in static sites are baked in at build time.

## Running Locally

```bash
runtm run          # Auto-detects runtime, uses Bun if available (3x faster)
```

## Before Deploy (REQUIRED)

**You MUST edit `runtm.discovery.yaml` before deploying:**

1. Replace ALL `# TODO:` placeholders with real content
2. Fill in: description, summary, capabilities, use_cases, tags
3. Static sites don't need the `api` section

**DO NOT deploy with `# TODO:` placeholders!**

## Deployment

```bash
# 1. Edit runtm.discovery.yaml first!
# 2. Then:
runtm status    # Check auth
runtm login     # If not authenticated
runtm validate  # Validate project
runtm deploy    # Deploy
```

## Constraints

- ❌ Don't change port from 3000
- ❌ Don't add API routes
- ❌ Don't use server components
- ❌ Don't delete `public/health`
- ❌ Don't remove `output: 'export'`
- ✅ Page-specific → `components/pages/`
- ✅ Reusable UI → `components/ui/`
