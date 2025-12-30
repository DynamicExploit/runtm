# Agent Instructions

This project is a Runtm static site. Instructions auto-apply in these AI IDEs:

| IDE | Auto-apply File |
|-----|-----------------|
| Cursor | `.cursor/rules/runtm.mdc` |
| Claude Code | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |

If you're using a different AI tool, follow the rules below.

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

Fast, zero-backend pages served as files. Perfect for content that doesn't need server-side rendering.

**Use cases:**
- Marketing website
- Product landing page/waitlist
- Docs/changelog
- Status/press page

## Critical Rules

1. **DO NOT change the port** - Must be 3000
2. **DO NOT add API routes** - This is a static export only
3. **DO NOT add server components** - Keep it static
4. **DO NOT remove runtm.yaml** - Required for deployment

## Project Structure

```
app/                         # Next.js App Router pages
├── layout.tsx               # Root layout
├── page.tsx                 # Homepage
└── globals.css              # Global styles

components/
├── layout/                  # App-wide layout components
│   ├── Header.tsx
│   └── Footer.tsx
├── pages/                   # Page-specific components & logic
│   └── home/
│       ├── index.ts         # Exports
│       ├── HomeHero.tsx     # Hero section
│       ├── HomeFeatures.tsx # Features section
│       └── HomeCTA.tsx      # Call-to-action section
├── sections/                # Legacy section components (optional)
└── ui/                      # Reusable UI components

public/
├── health                   # Health check endpoint (DO NOT DELETE)
├── images/                  # Static images
└── favicon.ico
```

## Component Organization

### Page-Specific Components (`components/pages/`)

Place components that are specific to a single page here:

```
components/pages/about/
├── index.ts
├── AboutHero.tsx
├── AboutTeam.tsx
└── AboutMission.tsx
```

### Reusable UI Components (`components/ui/`)

Place generic, reusable components here:

```tsx
// components/ui/Button.tsx
interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
}

export function Button({ children, variant = 'primary' }: ButtonProps) {
  const styles = variant === 'primary' 
    ? 'bg-[var(--accent)] text-[var(--background)]'
    : 'border border-[var(--border)]';
  
  return (
    <button className={`rounded-lg px-4 py-2 font-medium ${styles}`}>
      {children}
    </button>
  );
}
```

## Adding New Pages

### 1. Create Page Components

```
components/pages/pricing/
├── index.ts
├── PricingHero.tsx
├── PricingPlans.tsx
└── PricingFAQ.tsx
```

### 2. Create the Page

```tsx
// app/pricing/page.tsx
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { PricingHero, PricingPlans, PricingFAQ } from '@/components/pages/pricing';

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <PricingHero />
        <PricingPlans />
        <PricingFAQ />
      </main>
      <Footer />
    </div>
  );
}
```

## Styling

Use Tailwind CSS classes. Custom CSS variables are defined in `app/globals.css`:

- `--background` - Page background
- `--foreground` - Text color
- `--accent` - Brand/accent color
- `--muted` - Secondary text
- `--border` - Border color

## Images

Place images in `public/images/` and reference them:

```tsx
import Image from 'next/image';

<Image 
  src="/images/hero.png" 
  alt="Hero" 
  width={800} 
  height={600}
/>
```

## Running Locally

```bash
# Recommended: auto-detects runtime and port from runtm.yaml
# Uses Bun if available (3x faster), falls back to npm
runtm run

# Or manually with Bun (preferred for speed):
bun install
bun run dev

# Or with npm:
npm install
npm run dev
```

## Before Deploying (MANDATORY STEPS)

⚠️ **STOP: Complete ALL steps below before running `runtm deploy`.**

### Step 1: Update Discovery Metadata (REQUIRED)

**You MUST edit `runtm.discovery.yaml` and replace ALL `# TODO:` placeholders with real content.**

Example of a properly filled discovery file:

```yaml
description: |
  A marketing landing page for Acme Corp showcasing product features,
  pricing plans, and customer testimonials. Built with Next.js.

summary: "Acme Corp - Modern solutions for modern teams"

capabilities:
  - "Product feature showcase"
  - "Pricing comparison"
  - "Customer testimonials"
  - "Contact form"

use_cases:
  - "Potential customers evaluating the product"
  - "Existing customers looking for pricing info"

tags:
  - landing-page
  - marketing
  - saas
  - nextjs
```

**DO NOT deploy with `# TODO:` placeholders!** Apps with proper metadata are discoverable in the dashboard.

### Step 2: Authenticate (REQUIRED)

```bash
runtm status    # Check if logged in
runtm login     # If not authenticated, complete browser auth
```

### Step 3: Validate and Deploy

```bash
runtm validate  # Check project is valid
runtm deploy    # Deploy to production
```

### Deployment Checklist (follow in order)
1. ✅ Edit `runtm.discovery.yaml` - replace ALL `# TODO:` with real content
2. ✅ Run `runtm status` to check auth
3. ✅ If not authenticated, run `runtm login` and complete browser auth
4. ✅ Run `runtm validate` to check project
5. ✅ Run `runtm deploy` to deploy

### Common Errors
- **"nodename nor servname provided"** → Not logged in. Run `runtm login` first.
- **"Authentication required"** → Run `runtm login` first.
- **Network/DNS errors** → Run `runtm login` to configure the CLI.

## What NOT To Do

- ❌ Change port from 3000
- ❌ Add API routes (they don't work with static export)
- ❌ Use server components or server actions
- ❌ Delete `public/health` file
- ❌ Remove `output: 'export'` from next.config.js
- ❌ Put page-specific components in `ui/` (use `pages/`)
- ❌ Put reusable components in `pages/` (use `ui/`)
