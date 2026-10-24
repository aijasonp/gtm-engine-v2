/**
 * Google Sheets client for the GTM Executive Snapshot. Server-side only.
 *
 * Reads the "Weekly Forecast {{COMPANY}}" sheet:
 *   - Forecast Log tab    → weekly forecast calls (ForecastCall)
 *   - Quarter Reference   → active quarter label + roster/quota table (Quotas)
 *
 * Auth: OAuth refresh token (same Google account the GTM agent uses for Sheets access).
 * Env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN,
 *      GTM_FORECAST_SHEET_ID (defaults to the FY26 Q4 sheet).
 */
import type { ForecastCall, Quotas } from './types';
import { requiredEnv, optionalEnv } from './env';

const SHEETS_API = 'https://sheets.googleapis.com/v4/spreadsheets';
const TOKEN_API = 'https://oauth2.googleapis.com/token';

export const DEFAULT_SHEET_ID = 'REDACTED_GOOGLE_ID';

function sheetId() {
  return optionalEnv('GTM_FORECAST_SHEET_ID') ?? DEFAULT_SHEET_ID;
}

let cachedToken: { value: string; expiresAt: number } | null = null;

async function accessToken(): Promise<string> {
  const now = Date.now();
  if (cachedToken && cachedToken.expiresAt > now + 60_000) return cachedToken.value;
  const res = await fetch(TOKEN_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: requiredEnv('GOOGLE_CLIENT_ID'),
      client_secret: requiredEnv('GOOGLE_CLIENT_SECRET'),
      refresh_token: requiredEnv('GOOGLE_REFRESH_TOKEN'),
      grant_type: 'refresh_token'
    })
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Google token refresh failed: ${res.status} — ${body.slice(0, 300)}`);
  }
  const data = (await res.json()) as { access_token: string; expires_in: number };
  cachedToken = { value: data.access_token, expiresAt: now + data.expires_in * 1000 };
  return cachedToken.value;
}

async function getValues(range: string): Promise<string[][]> {
  const token = await accessToken();
  const url = `${SHEETS_API}/${sheetId()}/values/${encodeURIComponent(range)}?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=FORMATTED_STRING`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`Sheets values get "${range}" failed: ${res.status} — ${body.slice(0, 300)}`);
  }
  const data = (await res.json()) as { values?: (string | number)[][] };
  return (data.values ?? []).map((row) => row.map((c) => String(c)));
}

/** "Q4 FY26" → true; everything else (0, serials, blanks) → false. */
const isQuarterLabel = (s: string) => /^Q[1-4] FY\d{2}$/.test(s.trim());

/** US date ("10/2/2026") or ISO → YYYY-MM-DD, or null when unparseable. */
function toIsoDate(s: string): string | null {
  const t = s.trim();
  if (!t) return null;
  if (/^\d{4}-\d{2}-\d{2}/.test(t)) return t.slice(0, 10);
  const m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) {
    const [, mm, dd, yyyy] = m;
    return `${yyyy}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`;
  }
  return null;
}

/** "$250,000" / "250000" / 250000 → 250000 */
const toAmount = (s: string) => {
  const n = Number(s.replace(/[^0-9.\-]/g, ''));
  return Number.isFinite(n) ? n : 0;
};

const ROLES = ['AE', 'VP', 'CRO'] as const;

/** Forecast Log tab → ForecastCall rows (skips the header and incomplete rows). */
export async function fetchForecastCalls(): Promise<ForecastCall[]> {
  const rows = await getValues("'Forecast Log'!A2:I");
  const out: ForecastCall[] = [];
  for (const r of rows) {
    const [week, quarter, , name, , role, commit, best, pipeline] = r;
    const weekIso = toIsoDate(week ?? '');
    const roleNorm = (role ?? '').trim().toUpperCase() as ForecastCall['role'];
    if (!weekIso || !quarter || !name || !ROLES.includes(roleNorm)) continue;
    out.push({
      week: weekIso,
      quarter: quarter.trim(),
      name: name.trim(),
      role: roleNorm,
      commit: toAmount(commit ?? ''),
      best: toAmount(best ?? ''),
      pipeline: toAmount(pipeline ?? '')
    });
  }
  return out;
}

/**
 * Quarter Reference tab → Quotas keyed by quarter label.
 * Reads the "Active Quarter" cell and the "Roster & Quotas" table.
 *
 * Team quota rule (from the sheet's own footnote: "VP and CRO quotas are team-level"):
 * the VP and CRO quota figures are the SAME team-level quota, not additive.
 * So `_team` = the team-level figure carried by the VP/CRO rows, and each AE
 * keeps their individual quota. This reproduces the agreed metric inputs exactly
 * (e.g. Q4 FY26: AEs $250K each, _team $1M).
 */
export async function fetchQuotas(): Promise<Quotas> {
  const rows = await getValues("'Quarter Reference'!A1:E40");
  let quarter = '';
  let rosterHeader = -1;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if ((r[0] ?? '').trim() === 'Active Quarter' && isQuarterLabel(r[1] ?? '')) quarter = r[1].trim();
    if ((r[0] ?? '').startsWith('Name (exact HubSpot spelling)')) rosterHeader = i;
  }
  if (!quarter || rosterHeader === -1) return {};

  const quotas: Record<string, number> = {};
  let team = 0;
  for (let i = rosterHeader + 1; i < rows.length; i++) {
    const [name, , role, quotaCarrying, quota] = rows[i];
    const n = (name ?? '').trim();
    if (!n || n.startsWith('Open seat')) continue;
    if ((quotaCarrying ?? '').trim().toLowerCase() !== 'yes') continue;
    const q = toAmount(quota ?? '');
    quotas[n] = q;
    const r2 = (role ?? '').trim().toUpperCase();
    if (r2 === 'VP' || r2 === 'CRO') team = Math.max(team, q);
  }
  quotas._team = team;
  return { [quarter]: quotas };
}
