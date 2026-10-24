/**
 * Metric rules for the GTM Executive Snapshot. Pure functions, no UI.
 *
 * Rules (agreed in "Executive GTM Dashboard — Goals & Requirements"):
 *  - Pipeline = open deals (not Closed Won / Closed Lost) whose forecast category is not Not Forecasted (OMIT)
 *  - Bookings = Closed Won amount by close date; New Business + Upsell only
 *  - Forecast weeks run Tuesday–Monday, labeled by their Friday; a week belongs to the quarter its Friday is in
 *  - Fiscal year = calendar year
 *  - Deal age = days since the deal entered stage 1 (falls back to create date)
 */
import type { Deal, DealType, ForecastCategory } from './types';

export type Grain = 'week' | 'month' | 'quarter' | 'year';
export interface QuarterRef {
  y: number;
  q: number;
}

const DAY = 86_400_000;
export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const parseDate = (s: string) => new Date(`${s}T00:00:00Z`);
export const iso = (d: Date) => d.toISOString().slice(0, 10);
export const daysBetween = (a: Date, b: Date) => Math.round((b.getTime() - a.getTime()) / DAY);

/** Friday label of the Tue–Mon forecast week containing `d`. */
export function weekFriday(d: Date) {
  const sinceTuesday = (d.getUTCDay() - 2 + 7) % 7;
  return new Date(d.getTime() + (3 - sinceTuesday) * DAY);
}
export const quarterOf = (d: Date) => Math.floor(d.getUTCMonth() / 3) + 1;
export const fyLabel = (y: number) => `FY${String(y).slice(2)}`;
export const quarterLabel = ({ y, q }: QuarterRef) => `Q${q} ${fyLabel(y)}`;
export const nextQuarter = ({ y, q }: QuarterRef): QuarterRef => (q === 4 ? { y: y + 1, q: 1 } : { y, q: q + 1 });
export const prevQuarter = ({ y, q }: QuarterRef): QuarterRef => (q === 1 ? { y: y - 1, q: 4 } : { y, q: q - 1 });
export function parseQuarterLabel(label: string): QuarterRef {
  const [q, fy] = label.split(' ');
  return { y: 2000 + Number(fy.slice(2)), q: Number(q.slice(1)) };
}
/** Current quarter by the forecast rule (quarter of this week's Friday). */
export const currentQuarter = (asOf: Date): QuarterRef => {
  const f = weekFriday(asOf);
  return { y: f.getUTCFullYear(), q: quarterOf(f) };
};
export const inQuarter = (date: string, { y, q }: QuarterRef) => {
  const d = parseDate(date);
  return d.getUTCFullYear() === y && quarterOf(d) === q;
};

export const isPipeline = (d: Deal) => d.so < 6 && d.fc !== 'OMIT';
export const isWon = (d: Deal) => d.so === 6;
export type PipeCategory = 'COMMIT' | 'BEST_CASE' | 'PIPELINE';
export const pipeCategory = (fc: ForecastCategory): PipeCategory =>
  fc === 'COMMIT' ? 'COMMIT' : fc === 'BEST_CASE' ? 'BEST_CASE' : 'PIPELINE';
export const sum = (list: Deal[]) => list.reduce((s, d) => s + d.a, 0);
export const dealAge = (d: Deal, asOf: Date) => daysBetween(parseDate(d.s1 ?? d.cr), asOf);

export interface Filters {
  type: 'all' | DealType;
  owner: string; // 'all' or owner name
}
export const applyFilters = (deals: Deal[], f: Filters) =>
  deals.filter((d) => (f.type === 'all' || d.t === f.type) && (f.owner === 'all' || d.o === f.owner));

/** Bucket key + fiscal year a date falls into for a grain. */
export function bucketOf(d: Date, grain: Grain) {
  if (grain === 'week') {
    const f = weekFriday(d);
    return { key: iso(f), fy: f.getUTCFullYear() };
  }
  const y = d.getUTCFullYear();
  if (grain === 'month') return { key: `${y}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`, fy: y };
  if (grain === 'quarter') return { key: `${y}-Q${quarterOf(d)}`, fy: y };
  return { key: String(y), fy: y };
}

export interface Period {
  key: string;
  label: string; // axis label
  title: string; // tooltip / drill-down title
  fy: number;
}
/** All periods of a grain across fiscal years (for 'year', one period per year). */
export function periodsFor(grain: Grain, years: number[]): Period[] {
  if (grain === 'year') return years.map((y) => ({ key: String(y), label: fyLabel(y), title: fyLabel(y), fy: y }));
  return years.flatMap((fy) => {
    const tag = years.length > 1 ? ` '${String(fy).slice(2)}` : '';
    if (grain === 'quarter')
      return [1, 2, 3, 4].map((q) => ({
        key: `${fy}-Q${q}`,
        label: q === 1 ? `Q1${tag}` : `Q${q}`,
        title: `Q${q} ${fyLabel(fy)}`,
        fy
      }));
    if (grain === 'month')
      return MONTHS.map((m, i) => ({
        key: `${fy}-${String(i + 1).padStart(2, '0')}`,
        label: i === 0 ? `${m}${tag}` : m,
        title: `${m} ${fyLabel(fy)}`,
        fy
      }));
    const out: Period[] = [];
    let f = weekFriday(new Date(Date.UTC(fy, 0, 1)));
    if (f.getUTCFullYear() < fy) f = new Date(f.getTime() + 7 * DAY);
    while (f.getUTCFullYear() === fy) {
      out.push({
        key: iso(f),
        label: `${f.getUTCMonth() + 1}/${f.getUTCDate()}`,
        title: `Week ending Fri ${MONTHS[f.getUTCMonth()]} ${f.getUTCDate()}, ${fy}`,
        fy
      });
      f = new Date(f.getTime() + 7 * DAY);
    }
    return out;
  });
}

/** Group deals into periods; each row has one numeric column per series plus the deals behind it. */
export function bucketize<K extends string>(
  deals: Deal[],
  grain: Grain,
  periods: Period[],
  seriesOf: (d: Deal) => K
) {
  const rows = new Map(
    periods.map((p) => [p.key, { ...p, total: 0, count: 0, deals: [] as Deal[], values: {} as Record<K, number> }])
  );
  const outside: Deal[] = [];
  for (const d of deals) {
    const row = rows.get(bucketOf(parseDate(d.cd), grain).key);
    if (!row) {
      outside.push(d);
      continue;
    }
    const k = seriesOf(d);
    row.values[k] = (row.values[k] ?? 0) + d.a;
    row.total += d.a;
    row.count++;
    row.deals.push(d);
  }
  return { rows: [...rows.values()], outside };
}

export function groupBy<K extends string>(deals: Deal[], keyOf: (d: Deal) => string, seriesOf: (d: Deal) => K) {
  const m = new Map<string, { name: string; total: number; count: number; values: Record<K, number>; deals: Deal[] }>();
  for (const d of deals) {
    const k = keyOf(d);
    if (!m.has(k)) m.set(k, { name: k, total: 0, count: 0, values: {} as Record<K, number>, deals: [] });
    const g = m.get(k)!;
    const s = seriesOf(d);
    g.values[s] = (g.values[s] ?? 0) + d.a;
    g.total += d.a;
    g.count++;
    g.deals.push(d);
  }
  return [...m.values()];
}

/** Cumulative Closed Won by month for each fiscal year (current year stops at the as-of month). */
export function cumulativeByMonth(won: Deal[], years: number[], asOf: Date) {
  return MONTHS.map((m, i) => {
    const row: Record<string, number | string | null> = { month: m };
    for (const y of years) {
      if (y === asOf.getUTCFullYear() && i > asOf.getUTCMonth()) {
        row[fyLabel(y)] = null;
        continue;
      }
      row[fyLabel(y)] = sum(
        won.filter((d) => {
          const x = parseDate(d.cd);
          return x.getUTCFullYear() === y && x.getUTCMonth() <= i;
        })
      );
    }
    return row;
  });
}

export interface Signal {
  label: string;
  tone: 'critical' | 'warning' | 'good' | 'neutral';
}
export function dealSignals(d: Deal, asOf: Date): Signal[] {
  const out: Signal[] = [];
  if (parseDate(d.cd) < asOf) out.push({ label: 'Close date passed', tone: 'critical' });
  if (d.pc > 0) out.push({ label: `Pushed ${d.pc}×`, tone: 'warning' });
  const lra = d.lra ? daysBetween(parseDate(d.lra), asOf) : null;
  if (lra === null) out.push({ label: 'No rep activity logged', tone: 'warning' });
  else if (lra > 14) out.push({ label: `No rep activity ${lra}d`, tone: 'warning' });
  if (d.hs !== null)
    out.push({ label: `Health ${d.hs}`, tone: d.hs >= 70 ? 'good' : d.hs >= 40 ? 'neutral' : 'critical' });
  return out;
}

export function money(v: number) {
  const a = Math.abs(v);
  if (a >= 1e6) return `$${(v / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, '')}M`;
  if (a >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
}
export const moneyFull = (v: number) => `$${Math.round(v).toLocaleString('en-US')}`;
export function formatDate(s: string | null) {
  if (!s) return null;
  const d = parseDate(s);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}
export const hubspotDealUrl = (portal: string, id: string) =>
  `https://app.hubspot.com/contacts/${portal}/record/0-3/${id}`;

/** The period containing `ref` for a grain, and the one after it. */
export function currentAndNext(grain: Grain, ref: Date) {
  const y = ref.getUTCFullYear();
  const list = periodsFor(grain, [y - 1, y, y + 1]).map((p) => ({ ...p, title: p.title }));
  const key = bucketOf(ref, grain).key;
  const i = list.findIndex((p) => p.key === key);
  return { current: list[i], next: list[i + 1] };
}
