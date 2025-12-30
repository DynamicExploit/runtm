# My Site - Static Site Template

A beautiful static site built with Next.js and deployed on Runtm.

## What is a Static Site?

Fast, zero-backend pages served as files. Perfect for content that doesn't need server-side rendering.

**Use cases:**
- Marketing website
- Product landing page/waitlist
- Docs/changelog
- Status/press page

## Local Development

```bash
# Recommended: Use runtm run (auto-detects runtime and port)
runtm run

# Or manually:
npm install
npm run dev
```

### Other Commands

```bash
npm run build    # Build for production
npm run lint     # Lint code
npm run format   # Format code
```

## Deploy

⚠️ **Authentication is required before deploying.**

```bash
# Step 1: Check auth status
runtm status

# Step 2: Login (required once)
runtm login

# Step 3: Validate
runtm validate

# Step 4: Deploy to a live URL (uses starter tier by default)
runtm deploy

# Or deploy with a specific tier
runtm deploy --tier standard      # Medium tier (512MB RAM)
runtm deploy --tier performance  # High tier (1GB RAM, 2 CPUs)
```

### Machine Tiers

All deployments use **auto-stop** for cost savings (machines stop when idle and start automatically on traffic).

- **starter** (default): 1 shared CPU, 256MB RAM (~$2/month*)
- **standard**: 1 shared CPU, 512MB RAM (~$5/month*)
- **performance**: 2 shared CPUs, 1GB RAM (~$10/month*)

*Costs are estimates for 24/7 operation. With auto-stop, costs are much lower for low-traffic services.

You can also set the tier in `runtm.yaml`:

```yaml
name: my-site
template: static-site
runtime: node
tier: starter  # Options: starter, standard, performance
```

## Project Structure

```
app/
├── layout.tsx        # Root layout, metadata
├── page.tsx          # Homepage
├── globals.css       # Global styles
└── health/
    └── route.ts      # Health check endpoint

components/
├── layout/           # Layout components (header, footer)
├── sections/         # Page sections (hero, features, cta)
└── ui/               # Reusable UI components
```

## Customization

### Colors

Edit `tailwind.config.js` to customize the color palette:

```js
theme: {
  extend: {
    colors: {
      brand: {
        500: '#22c55e', // Your brand color
      },
    },
  },
},
```

Or update CSS variables in `app/globals.css`:

```css
:root {
  --accent: #22c55e;
}
```

### Typography

Fonts are configured in `app/layout.tsx`. Change the imported fonts to customize typography.

### Content

Edit the components in `components/sections/` to update content:
- `Hero.tsx` - Main headline and CTA
- `Features.tsx` - Feature cards
- `CTA.tsx` - Bottom call-to-action section

## Static Export

This template uses Next.js static export (`output: 'export'`). This means:
- No server-side code or API routes
- All pages are pre-rendered at build time
- Fast, secure, and easy to deploy
