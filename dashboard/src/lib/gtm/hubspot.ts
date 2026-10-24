/**
 * HubSpot CRM client for the GTM Executive Snapshot. Server-side only.
 *
 * Pulls the exact deal set defined in the handoff:
 *   object DEAL, pipeline = "default" (Sales Pipeline),
 *   dealtype IN (newbusiness, Upsell), dealstage != closedlost
 * and maps each record into the `Deal` shape used by the dashboard.
 * Owner IDs are resolved to names with the owners API (archived owners included).
 */
import type { Deal, DealType, ForecastCategory } from './types';
import { requiredEnv } from './env';

const API = 'https://api.hubapi.com';

const DEAL_PROPERTIES = [
  'dealname',
  'amount_in_home_currency',
  'dealstage',
  'hs_manual_forecast_category',
  'closedate',
  'createdate',
  'deal_age_from_stage_1',
  'dealtype',
  'hubspot_owner_id',
  'hs_next_step',
  'last_rep_activity_date',
  'notes_last_updated',
  'notes_next_activity_date',
  'close_date_push_count',
  'original_close_date',
  'deal_health_score',
  'hs_v2_date_entered_current_stage'
] as const;

interface HubSpotDeal {
  id: string;
  properties: Record<(typeof DEAL_PROPERTIES)[number] | string, string | null>;
}

interface StageInfo {
  label: string;
  order: number;
}

function token() {
  return requiredEnv('HUBSPOT_TOKEN');
}

async function hsFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token()}`,
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HubSpot ${path} failed: ${res.status} ${res.statusText} — ${body.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

/** stage id → { label, displayOrder } for the Sales Pipeline. */
async function fetchStageMap(): Promise<Map<string, StageInfo>> {
  const data = await hsFetch<{ results: { id: string; stages: { id: string; label: string; displayOrder: number }[] }[] }>(
    '/crm/v3/pipelines/deals'
  );
  const pipeline = data.results.find((p) => p.id === 'default');
  if (!pipeline) throw new Error('HubSpot pipeline "default" (Sales Pipeline) not found');
  return new Map(pipeline.stages.map((s) => [s.id, { label: s.label, order: s.displayOrder }]));
}

/** All deals matching the handoff filters, following search pagination. */
async function searchDeals(): Promise<HubSpotDeal[]> {
  const out: HubSpotDeal[] = [];
  let after: string | undefined;
  do {
    const body: Record<string, unknown> = {
      filterGroups: [
        {
          filters: [
            { propertyName: 'pipeline', operator: 'EQ', value: 'default' },
            { propertyName: 'dealtype', operator: 'IN', values: ['newbusiness', 'Upsell'] },
            { propertyName: 'dealstage', operator: 'NEQ', value: 'closedlost' }
          ]
        }
      ],
      properties: [...DEAL_PROPERTIES],
      limit: 100
    };
    if (after) body.after = after;
    const page = await hsFetch<{
      results: HubSpotDeal[];
      paging?: { next?: { after?: string } };
    }>('/crm/v3/objects/deals/search', { method: 'POST', body: JSON.stringify(body) });
    out.push(...page.results);
    after = page.paging?.next?.after;
  } while (after);
  return out;
}

/** owner id → "First Last"; includes archived owners so departed reps still resolve. */
async function fetchOwnerMap(): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  for (const archived of [false, true]) {
    let after: string | undefined;
    do {
      const qs = new URLSearchParams({ limit: '100', archived: String(archived) });
      if (after) qs.set('after', after);
      const page = await hsFetch<{
        results: { id: string; firstName?: string; lastName?: string; email?: string }[];
        paging?: { next?: { after?: string } };
      }>(`/crm/v3/owners/?${qs.toString()}`);
      for (const o of page.results) {
        const name = [o.firstName, o.lastName].filter(Boolean).join(' ').trim();
        map.set(o.id, name || o.email || `Owner ${o.id}`);
      }
      after = page.paging?.next?.after;
    } while (after);
  }
  return map;
}

/** HubSpot timestamp or date string → YYYY-MM-DD (null-safe). */
const day = (v: string | null | undefined) => (v ? v.slice(0, 10) : null);
const num = (v: string | null | undefined) => {
  if (!v) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const FORECAST_CATEGORIES: ForecastCategory[] = ['COMMIT', 'BEST_CASE', 'PIPELINE', 'OMIT', 'CLOSED', ''];

function mapDeal(raw: HubSpotDeal, stages: Map<string, StageInfo>, owners: Map<string, string>): Deal {
  const p = raw.properties;
  const stage = stages.get(p.dealstage ?? '');
  const fcRaw = p.hs_manual_forecast_category ?? '';
  const fc = (FORECAST_CATEGORIES.includes(fcRaw as ForecastCategory) ? fcRaw : '') as ForecastCategory;
  const t: DealType = p.dealtype === 'Upsell' ? 'UP' : 'NB';
  return {
    id: raw.id,
    n: p.dealname ?? '(unnamed deal)',
    a: num(p.amount_in_home_currency) ?? 0,
    st: stage?.label ?? p.dealstage ?? 'Unknown',
    so: stage?.order ?? 0,
    fc,
    cd: day(p.closedate) ?? '',
    cr: day(p.createdate) ?? '',
    s1: day(p.deal_age_from_stage_1),
    t,
    o: owners.get(p.hubspot_owner_id ?? '') ?? 'Unassigned',
    ns: p.hs_next_step ?? null,
    lra: day(p.last_rep_activity_date),
    la: day(p.notes_last_updated),
    na: day(p.notes_next_activity_date),
    pc: num(p.close_date_push_count) ?? 0,
    ocd: day(p.original_close_date),
    hs: num(p.deal_health_score),
    eis: day(p.hs_v2_date_entered_current_stage)
  };
}

/** Live deal set from HubSpot, mapped to dashboard shape. */
export async function fetchDeals(): Promise<Deal[]> {
  const [stages, owners, deals] = await Promise.all([fetchStageMap(), fetchOwnerMap(), searchDeals()]);
  return deals.map((d) => mapDeal(d, stages, owners));
}
