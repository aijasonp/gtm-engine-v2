/**
 * Data shapes for the GTM Executive Snapshot.
 * Every data source (HubSpot, Forecast Log sheet, later Lemlist) is mapped into these types
 * in `data-source.ts`, so the dashboard never talks to an API directly.
 */

export type DealType = 'NB' | 'UP'; // New Business | Upsell
export type ForecastCategory = 'COMMIT' | 'BEST_CASE' | 'PIPELINE' | 'OMIT' | 'CLOSED' | '';

export interface Deal {
  id: string; // HubSpot record ID
  n: string; // deal name
  a: number; // amount (amount_in_home_currency)
  st: string; // stage label
  so: number; // stage order; 6 = Closed Won
  fc: ForecastCategory; // hs_manual_forecast_category (OMIT = Not Forecasted)
  cd: string; // close date YYYY-MM-DD
  cr: string; // create date
  s1: string | null; // deal_age_from_stage_1 (date entered stage 1)
  t: DealType;
  o: string; // owner name
  ns: string | null; // hs_next_step
  lra: string | null; // last_rep_activity_date
  la: string | null; // notes_last_updated
  na: string | null; // notes_next_activity_date
  pc: number; // close_date_push_count
  ocd: string | null; // original_close_date
  hs: number | null; // deal_health_score
  eis: string | null; // hs_v2_date_entered_current_stage
}

/** One row of the Forecast Log tab (only these 7 columns are read). */
export interface ForecastCall {
  week: string; // Friday of the Tue–Mon forecast week, YYYY-MM-DD
  quarter: string; // e.g. "Q4 FY26"
  name: string;
  role: 'AE' | 'VP' | 'CRO';
  commit: number;
  best: number;
  pipeline: number;
}

/** Quotas by quarter label. `_team` is the team quota; other keys are owner names. */
export type Quotas = Record<string, Record<string, number>>;

export interface Snapshot {
  asOf: string;
  portal: string; // HubSpot portal ID, for record links
  deals: Deal[];
  calls: ForecastCall[];
  quotas: Quotas;
}
