'use client';

import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Deal } from '@/lib/gtm/types';
import {
  currentQuarter,
  dealAge,
  dealSignals,
  daysBetween,
  formatDate,
  hubspotDealUrl,
  inQuarter,
  isPipeline,
  money,
  nextQuarter,
  parseDate,
  parseQuarterLabel,
  pipeCategory,
  quarterLabel,
  sum
} from '@/lib/gtm/metrics';
import { ColorScope, Section, SignalBadge, SimpleSelect, categoryConfig } from './shared';

type SortKey = 'a' | 'cd' | 'age' | 'pc';

export function DealsSection({ deals, asOf, portal }: { deals: Deal[]; asOf: Date; portal: string }) {
  const cq = currentQuarter(asOf);
  const quarters = [cq, nextQuarter(cq), nextQuarter(nextQuarter(cq)), nextQuarter(nextQuarter(nextQuarter(cq)))].map(quarterLabel);
  const [closing, setClosing] = React.useState('all');
  const [sort, setSort] = React.useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'a', dir: -1 });
  const [showAll, setShowAll] = React.useState(false);
  const [open, setOpen] = React.useState<Deal | null>(null);

  let list = deals.filter(isPipeline);
  if (closing !== 'all') list = list.filter((d) => inQuarter(d.cd, parseQuarterLabel(closing)));
  const val = (d: Deal) => (sort.key === 'age' ? dealAge(d, asOf) : sort.key === 'cd' ? parseDate(d.cd).getTime() : d[sort.key]);
  list = [...list].sort((a, b) => (val(a) - val(b)) * sort.dir);
  const shown = showAll ? list : list.slice(0, 10);

  const th = (key: SortKey, label: string, className = '') => (
    <TableHead className={className}>
      <button
        type='button'
        className='hover:text-foreground inline-flex items-center gap-1'
        onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : key === 'cd' ? 1 : -1 }))}
        aria-label={`Sort by ${label}`}
      >
        {label}
        {sort.key === key && <span aria-hidden>{sort.dir === 1 ? '↑' : '↓'}</span>}
      </button>
    </TableHead>
  );

  return (
    <Section
      id='deals'
      title='Deal status'
      description='Open forecasted deals with the signals an exec would ask about. Select a deal for detail.'
      controls={
        <SimpleSelect
          label='Closing'
          value={closing}
          options={[{ value: 'all', label: 'Any quarter' }, ...quarters.map((q) => ({ value: q, label: q }))]}
          onChange={(v) => { setClosing(v); setShowAll(false); }}
        />
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>
            {showAll || list.length <= 10 ? 'All' : 'Top 10 of'} {list.length} open deals
          </CardTitle>
          <CardDescription>
            {money(sum(list))} total{closing !== 'all' && ` closing ${closing}`}
          </CardDescription>
        </CardHeader>
        <CardContent className='flex flex-col gap-3'>
          <ColorScope config={categoryConfig} className='overflow-x-auto'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Deal</TableHead>
                  {th('a', 'Amount', 'text-right')}
                  <TableHead className='hidden md:table-cell'>Stage · Category</TableHead>
                  {th('cd', 'Close date', 'hidden sm:table-cell')}
                  {th('age', 'Age', 'hidden lg:table-cell text-right')}
                  <TableHead className='hidden lg:table-cell'>Signals</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((d) => {
                  const cat = pipeCategory(d.fc);
                  return (
                    <TableRow
                      key={d.id}
                      className='cursor-pointer'
                      tabIndex={0}
                      onClick={() => setOpen(d)}
                      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setOpen(d))}
                    >
                      <TableCell className='max-w-64 whitespace-normal'>
                        <div className='font-medium'>{d.n}</div>
                        <div className='text-muted-foreground text-xs'>
                          {d.o} · {d.t === 'NB' ? 'New Business' : 'Upsell'}
                          <span className='sm:hidden'> · closes {formatDate(d.cd)}</span>
                        </div>
                        <div className='mt-1 flex flex-wrap gap-1 lg:hidden'>
                          {dealSignals(d, asOf).map((s) => <SignalBadge key={s.label} s={s} />)}
                        </div>
                      </TableCell>
                      <TableCell className='text-right align-top tabular-nums'>{money(d.a)}</TableCell>
                      <TableCell className='hidden align-top md:table-cell'>
                        <div>{d.st}</div>
                        <Badge variant='outline' className='mt-1'>
                          <span className='size-2 rounded-[2px]' style={{ background: `var(--color-${cat})` }} />
                          {categoryConfig[cat].label}
                        </Badge>
                      </TableCell>
                      <TableCell className='hidden align-top tabular-nums sm:table-cell'>
                        {formatDate(d.cd)}
                        {d.pc > 0 && (
                          <div className='text-muted-foreground text-xs'>{d.ocd ? `was ${formatDate(d.ocd)}` : `pushed ${d.pc}×`}</div>
                        )}
                      </TableCell>
                      <TableCell className='hidden text-right align-top tabular-nums lg:table-cell'>{dealAge(d, asOf)}d</TableCell>
                      <TableCell className='hidden align-top lg:table-cell'>
                        <div className='flex max-w-72 flex-wrap gap-1'>
                          {dealSignals(d, asOf).map((s) => <SignalBadge key={s.label} s={s} />)}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {!shown.length && (
                  <TableRow>
                    <TableCell colSpan={6} className='text-muted-foreground'>No open deals match these filters.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ColorScope>
          {list.length > 10 && (
            <Button variant='outline' size='sm' className='self-start' onClick={() => setShowAll((s) => !s)}>
              {showAll ? 'Show top 10' : `Show all ${list.length}`}
            </Button>
          )}
        </CardContent>
      </Card>

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent className='w-full overflow-y-auto sm:max-w-md'>
          {open && <DealDetail d={open} asOf={asOf} portal={portal} />}
        </SheetContent>
      </Sheet>
    </Section>
  );
}

function DealDetail({ d, asOf, portal }: { d: Deal; asOf: Date; portal: string }) {
  const ago = (s: string | null) => (s ? `${formatDate(s)} (${daysBetween(parseDate(s), asOf)}d ago)` : null);
  const rows: [string, string | null, string][] = [
    ['Next step', d.ns, 'Not entered'],
    ['Next activity', formatDate(d.na), 'None scheduled'],
    ['Last rep activity', ago(d.lra), 'Not logged'],
    ['Last activity (any)', ago(d.la), 'None'],
    ['In current stage', d.eis ? `${daysBetween(parseDate(d.eis), asOf)} days (since ${formatDate(d.eis)})` : null, 'Unknown'],
    ['Close date', `${formatDate(d.cd)}${d.pc ? ` · pushed ${d.pc}×` : ''}`, ''],
    ['Original close date', formatDate(d.ocd), 'Not captured'],
    ['Deal age', `${dealAge(d, asOf)} days${d.s1 ? '' : ' (from create date)'}`, ''],
    ['Deal health', d.hs !== null ? `${d.hs} / 100` : null, 'Not scored']
  ];
  return (
    <>
      <SheetHeader>
        <SheetTitle className='pr-8'>{d.n}</SheetTitle>
        <SheetDescription>
          {money(d.a)} · {d.st} · {d.o}
        </SheetDescription>
        <div className='flex flex-wrap gap-1 pt-1'>
          {dealSignals(d, asOf).map((s) => <SignalBadge key={s.label} s={s} />)}
        </div>
      </SheetHeader>
      <dl className='grid grid-cols-1 gap-3 px-4 sm:grid-cols-2'>
        {rows.map(([k, v, missing]) => (
          <div key={k}>
            <dt className='text-muted-foreground text-xs font-medium'>{k}</dt>
            <dd className={v ? 'text-sm' : 'text-muted-foreground text-sm italic'}>{v ?? missing}</dd>
          </div>
        ))}
      </dl>
      <div className='text-muted-foreground mx-4 rounded-lg border border-dashed p-3 text-sm'>
        <p className='text-foreground font-medium'>Call brief summary</p>
        <p className='mt-1'>Placeholder for a 2–3 line summary of the GTM agent&apos;s latest call brief. There&apos;s no HubSpot field for it yet.</p>
      </div>
      <div className='px-4 pb-6'>
        <Button nativeButton={false} render={<a href={hubspotDealUrl(portal, d.id)} target='_blank' rel='noopener noreferrer' />}>
          Open in HubSpot
        </Button>
      </div>
    </>
  );
}
