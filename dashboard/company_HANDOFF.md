# {{COMPANY}} GTM Executive Snapshot — handoff for the GTM agent

Built on [next-shadcn-dashboard-starter](https://github.com/Kiranism/next-shadcn-dashboard-starter) (MIT). License file kept in the repo.

## What's done
- Paid and demo features removed with the starter's cleanup script: Clerk, Sentry, AI chat, kanban, chat, notifications, demo pages and mock APIs.
- One scrolling page at `/dashboard/gtm`: Pipeline, Bookings, Forecast, Deal status.
- Global filters: deal type and owner. Each section has its own time controls.
- All metric rules live in `src/lib/gtm/metrics.ts`; data shapes in `src/lib/gtm/types.ts`.
- Data comes from one place: `src/lib/gtm/data-source.ts` (currently a HubSpot snapshot JSON pulled 9/30/2026).

## What the GTM agent needs to do
1. **Live data:** replace `getSnapshot()` in `src/lib/gtm/data-source.ts` with server-side calls. The file lists the exact HubSpot filters and properties, the Forecast Log columns, and where quotas come from. Keep API keys on the server.
2. **Login:** add Better Auth (MIT) with Google sign-in, an admin-managed access list, and roles (Admin / Exec / Rep). The gate goes in `src/app/dashboard/layout.tsx` (marked TODO). Enforce roles on the server so a rep never receives other reps' deals.
3. **Weekly snapshots:** store one HubSpot snapshot per Tue–Mon week to power "Category changes this week."
4. **Deploy** to {{COMPANY}}'s Vercel team.
5. **Later:** Lemlist connector; Marketing, CS, and Finance pages (add them to `src/config/nav-config.ts`).

## Run locally
```
npm install
npm run dev   # http://localhost:3000 redirects to /dashboard/gtm
```

## Preview build (optional)
`preview/` bundles the page into a single HTML file with esbuild + Tailwind for the Claude preview. Not used in production.
