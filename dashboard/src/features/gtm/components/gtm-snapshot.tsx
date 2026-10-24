'use client';

import * as React from 'react';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { Snapshot } from '@/lib/gtm/types';
import { type Filters, applyFilters, formatDate, parseDate } from '@/lib/gtm/metrics';
import { SimpleSelect } from './shared';
import { PipelineSection } from './pipeline-section';
import { BookingsSection } from './bookings-section';
import { ForecastSection } from './forecast-section';
import { DealsSection } from './deals-section';

const SECTIONS = [
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'bookings', label: 'Bookings' },
  { id: 'forecast', label: 'Forecast' },
  { id: 'deals', label: 'Deal status' }
];

/** GTM Executive Snapshot: one scrolling page. Deal type and owner apply to every section;
 *  each section owns its time controls. */
export function GtmSnapshot({ snapshot }: { snapshot: Snapshot }) {
  const asOf = parseDate(snapshot.asOf);
  const [filters, setFilters] = React.useState<Filters>({ type: 'all', owner: 'all' });
  const owners = React.useMemo(() => [...new Set(snapshot.deals.map((d) => d.o))].sort(), [snapshot.deals]);
  const deals = applyFilters(snapshot.deals, filters);

  return (
    <div className='flex flex-1 flex-col gap-8 p-4 md:px-6'>
      <header className='flex flex-col gap-3'>
        <div className='flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>GTM Executive Snapshot Dashboard</h1>
            <p className='text-muted-foreground mt-1 text-sm'>
              HubSpot as of {formatDate(snapshot.asOf)} · Sales Pipeline · New Business + Upsell
            </p>
          </div>
          <nav aria-label='Sections' className='flex flex-wrap gap-1 text-sm'>
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className='text-muted-foreground hover:bg-muted hover:text-foreground rounded-md px-2.5 py-1'>
                {s.label}
              </a>
            ))}
          </nav>
        </div>

        <div className='bg-background/80 sticky top-16 z-10 -mx-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-y px-4 py-2 backdrop-blur md:top-14 md:-mx-6 md:px-6'>
          <span className='text-primary text-xs font-semibold tracking-wide uppercase'>All sections</span>
          <div className='flex items-center gap-2'>
            <span className='text-muted-foreground text-xs font-medium'>Deal type</span>
            <ToggleGroup
              variant='outline'
              size='sm'
              spacing={0}
              aria-label='Deal type'
              value={[filters.type]}
              onValueChange={(v) => v[0] && setFilters((f) => ({ ...f, type: v[0] as Filters['type'] }))}
            >
              <ToggleGroupItem value='all'>Both</ToggleGroupItem>
              <ToggleGroupItem value='NB'>New Business</ToggleGroupItem>
              <ToggleGroupItem value='UP'>Upsell</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <SimpleSelect
            label='Owner'
            value={filters.owner}
            options={[{ value: 'all', label: 'All owners' }, ...owners.map((o) => ({ value: o, label: o }))]}
            onChange={(owner) => setFilters((f) => ({ ...f, owner }))}
            className='min-w-40'
          />
        </div>
      </header>

      <PipelineSection deals={deals} asOf={asOf} portal={snapshot.portal} />
      <BookingsSection deals={deals} asOf={asOf} portal={snapshot.portal} typeFilter={filters.type} />
      <ForecastSection deals={deals} calls={snapshot.calls} quotas={snapshot.quotas} asOf={asOf} owner={filters.owner} />
      <DealsSection deals={deals} asOf={asOf} portal={snapshot.portal} />

      <footer className='text-muted-foreground grid grid-cols-1 gap-4 border-t pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4'>
        <div>
          <p className='text-foreground font-medium'>Pipeline</p>
          <p>Open deals in the Sales Pipeline, excluding forecast category Not Forecasted (OMIT).</p>
        </div>
        <div>
          <p className='text-foreground font-medium'>Bookings</p>
          <p>Closed Won amount by close date. New Business and Upsell only; Renewals and Services excluded.</p>
        </div>
        <div>
          <p className='text-foreground font-medium'>Weeks and fiscal year</p>
          <p>Weeks run Tuesday to Monday, labeled by their Friday. FY = calendar year.</p>
        </div>
        <div>
          <p className='text-foreground font-medium'>Deal age</p>
          <p>Days since the deal entered stage 1 (falls back to create date).</p>
        </div>
      </footer>
    </div>
  );
}
