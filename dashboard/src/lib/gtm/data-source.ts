/**
 * DATA SOURCE — the only place the dashboard gets data from.
 *
 * Live mode (default when HUBSPOT_TOKEN is set):
 *   - deals  → HubSpot CRM search API, object DEAL, filters:
 *              pipeline = "default" (Sales Pipeline), dealtype IN (newbusiness, Upsell), dealstage != closedlost
 *              (full property list in hubspot.ts; owner IDs resolved via the owners API)
 *   - calls  → Forecast Log tab of the "Weekly Forecast {{COMPANY}}" Google Sheet (see sheets.ts)
 *   - quotas → Quarter Reference tab of the same sheet
 *
 * Snapshot mode (fallback for local dev without credentials):
 *   set GTM_DATA_SOURCE=snapshot to read src/data/gtm-snapshot.json instead.
 *
 * Responses are cached for GTM_CACHE_SECONDS (default 300) so a page view does not
 * re-hit HubSpot/Sheets on every request. All keys stay on the server.
 */
import { unstable_cache } from 'next/cache';
import type { Snapshot } from './types';
import { fetchDeals } from './hubspot';
import { fetchForecastCalls, fetchQuotas } from './sheets';
import { optionalEnv } from './env';

const PORTAL = optionalEnv('HUBSPOT_PORTAL_ID') ?? '0000000';

async function liveSnapshot(): Promise<Snapshot> {
  const [deals, calls, quotas] = await Promise.all([fetchDeals(), fetchForecastCalls(), fetchQuotas()]);
  return {
    asOf: new Date().toISOString().slice(0, 10),
    portal: PORTAL,
    deals,
    calls,
    quotas
  };
}

async function fileSnapshot(): Promise<Snapshot> {
  const snapshot = (await import('@/data/gtm-snapshot.json')).default;
  return snapshot as Snapshot;
}

const cacheSeconds = () => {
  const n = Number(optionalEnv('GTM_CACHE_SECONDS') ?? '300');
  return Number.isFinite(n) && n > 0 ? n : 300;
};

const cachedLive = unstable_cache(liveSnapshot, ['gtm-live-snapshot'], { revalidate: cacheSeconds() });

export async function getSnapshot(): Promise<Snapshot> {
  const mode = optionalEnv('GTM_DATA_SOURCE');
  if (mode === 'snapshot' || !optionalEnv('HUBSPOT_TOKEN')) return fileSnapshot();
  return cachedLive();
}
