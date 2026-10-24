'use client';

import * as React from 'react';
import { Bar, BarChart, ReferenceLine, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { Deal, ForecastCall, Quotas } from '@/lib/gtm/types';
import {
  currentQuarter,
  formatDate,
  groupBy,
  inQuarter,
  isPipeline,
  isWon,
  money,
  nextQuarter,
  parseQuarterLabel,
  pipeCategory,
  prevQuarter,
  quarterLabel,
  sum
} from '@/lib/gtm/metrics';
import { ColorScope, EmptyNote, Kpi, KpiGrid, Legend, Section, SimpleSelect, WON_COLOR, categoryConfig } from './shared';

const barConfig = {
  WON: { label: 'Closed Won', theme: WON_COLOR },
  ...categoryConfig
} satisfies ChartConfig;
type Key = keyof typeof barConfig;
const KEYS: Key[] = ['WON', 'COMMIT', 'BEST_CASE', 'PIPELINE'];

export function ForecastSection({
  deals,
  calls,
  quotas,
  asOf,
  owner
}: {
  deals: Deal[];
  calls: ForecastCall[];
  quotas: Quotas;
  asOf: Date;
  owner: string;
}) {
  const cq = currentQuarter(asOf);
  const options = React.useMemo(() => {
    let q = prevQuarter(prevQuarter(cq));
    return Array.from({ length: 6 }, () => {
      const o = { value: quarterLabel(q), label: quarterLabel(q) + (quarterLabel(q) === quarterLabel(cq) ? ' (current)' : '') };
      q = nextQuarter(q);
      return o;
    });
  }, [cq.y, cq.q]); // eslint-disable-line react-hooks/exhaustive-deps
  const [quarter, setQuarter] = React.useState(quarterLabel(cq));
  const q = parseQuarterLabel(quarter);

  const list = deals.filter((d) => inQuarter(d.cd, q));
  const won = list.filter(isWon);
  const open = list.filter(isPipeline);
  const totals: Record<Key, number> = {
    WON: sum(won),
    COMMIT: sum(open.filter((d) => d.fc === 'COMMIT')),
    BEST_CASE: sum(open.filter((d) => d.fc === 'BEST_CASE')),
    PIPELINE: sum(open.filter((d) => pipeCategory(d.fc) === 'PIPELINE'))
  };
  const Q = quotas[quarter] ?? {};
  const quota = owner === 'all' ? Q._team : Q[owner];
  const openTotal = totals.COMMIT + totals.BEST_CASE + totals.PIPELINE;
  const left = quota !== undefined ? quota - totals.WON : undefined;

  const byOwner = groupBy(list.filter((d) => isWon(d) || isPipeline(d)), (d) => d.o, (d) => (isWon(d) ? 'WON' : pipeCategory(d.fc)) as Key).sort(
    (a, b) => b.total - a.total
  );

  const qCalls = calls.filter((c) => c.quarter === quarter);
  const latestWeek = qCalls.map((c) => c.week).sort().pop();
  const weekCalls = qCalls.filter((c) => c.week === latestWeek);
  const aeRollup = weekCalls
    .filter((c) => c.role === 'AE')
    .reduce((a, c) => ({ commit: a.commit + c.commit, best: a.best + c.best, pipeline: a.pipeline + c.pipeline }), { commit: 0, best: 0, pipeline: 0 });

  return (
    <Section
      id='forecast'
      title='Forecast'
      description='Where the quarter stands against quota, from HubSpot forecast categories and weekly calls.'
      controls={<SimpleSelect label='Quarter' value={quarter} options={options} onChange={setQuarter} />}
    >
      <KpiGrid>
        <Kpi
          label='Quota'
          value={quota !== undefined ? money(quota) : 'Not set'}
          footer={quota !== undefined ? (owner === 'all' ? 'Team (4 AEs × $250K)' : owner) : 'Add it in the forecast tracker'}
        />
        <Kpi label='Closed Won' value={money(totals.WON)} footer={quota ? `${Math.round((totals.WON / quota) * 100)}% of quota` : `${won.length} deals`} />
        <Kpi
          label='Commit (HubSpot)'
          value={money(totals.COMMIT)}
          footer={quota ? `Won + Commit = ${Math.round(((totals.WON + totals.COMMIT) / quota) * 100)}% of quota` : `${open.filter((d) => d.fc === 'COMMIT').length} deals`}
        />
        <Kpi
          label='Coverage'
          value={left && left > 0 ? `${(openTotal / left).toFixed(1)}×` : '—'}
          footer={left && left > 0 ? `${money(openTotal)} open ÷ ${money(left)} left to close` : 'Needs a quota'}
        />
      </KpiGrid>

      <div className='grid grid-cols-1 items-start gap-4 xl:grid-cols-3'>
        <Card className='xl:col-span-2'>
          <CardHeader>
            <CardTitle>{quarter} vs. quota</CardTitle>
            <CardDescription>Closed Won plus open pipeline by forecast category</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            <ChartContainer config={barConfig} className='aspect-auto h-24 w-full'>
              <BarChart layout='vertical' data={[{ name: quarter, ...totals }]} margin={{ left: 0, right: 16, top: 18 }}>
                <XAxis type='number' tickLine={false} axisLine={false} tickFormatter={money} domain={[0, (max: number) => Math.max(max, quota ?? 0) * 1.05]} />
                <YAxis type='category' dataKey='name' hide />
                <ChartTooltip
                  cursor={false}
                  content={
                    <ChartTooltipContent
                      formatter={(v, name) => (
                        <div className='flex w-full justify-between gap-4'>
                          <span className='text-muted-foreground'>{barConfig[name as Key]?.label}</span>
                          <span className='font-mono tabular-nums'>{money(Number(v))}</span>
                        </div>
                      )}
                    />
                  }
                />
                {KEYS.map((k) => (
                  <Bar key={k} dataKey={k} stackId='a' fill={`var(--color-${k})`} barSize={28} />
                ))}
                {quota !== undefined && (
                  <ReferenceLine x={quota} stroke='var(--foreground)' strokeWidth={2} label={{ value: `Quota ${money(quota)}`, position: 'top', fill: 'var(--foreground)', fontSize: 11 }} />
                )}
              </BarChart>
            </ChartContainer>
            <ColorScope config={barConfig}><Legend config={barConfig} /></ColorScope>
            <div className='overflow-x-auto'>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Owner</TableHead>
                    <TableHead className='text-right'>Quota</TableHead>
                    <TableHead className='text-right'>Won</TableHead>
                    <TableHead className='text-right'>Commit</TableHead>
                    <TableHead className='text-right'>Best Case</TableHead>
                    <TableHead className='text-right'>Pipeline</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {byOwner.map((r) => (
                    <TableRow key={r.name}>
                      <TableCell>{r.name}</TableCell>
                      <TableCell className='text-right tabular-nums'>{Q[r.name] !== undefined ? money(Q[r.name]) : '—'}</TableCell>
                      {KEYS.map((k) => (
                        <TableCell key={k} className='text-right tabular-nums'>{money(r.values[k] ?? 0)}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                  {!byOwner.length && (
                    <TableRow>
                      <TableCell colSpan={6} className='text-muted-foreground'>No open or won deals close in {quarter} for these filters.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
                {byOwner.length > 0 && (
                  <TableFooter>
                    <TableRow>
                      <TableCell>Total</TableCell>
                      <TableCell className='text-right tabular-nums'>{quota !== undefined ? money(quota) : '—'}</TableCell>
                      {KEYS.map((k) => (
                        <TableCell key={k} className='text-right tabular-nums'>{money(totals[k])}</TableCell>
                      ))}
                    </TableRow>
                  </TableFooter>
                )}
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Forecast calls</CardTitle>
            <CardDescription>From the Forecast Log: AE roll-up, VP, and CRO</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            {weekCalls.length ? (
              <>
                <p className='text-muted-foreground text-xs'>Week ending {formatDate(latestWeek ?? null)}</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Caller</TableHead>
                      <TableHead className='text-right'>Commit</TableHead>
                      <TableHead className='text-right'>Best Case</TableHead>
                      <TableHead className='text-right'>Pipeline</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[{ name: 'AE roll-up', ...aeRollup }, ...weekCalls.filter((c) => c.role !== 'AE').map((c) => ({ ...c, name: `${c.name} (${c.role})` }))].map((r) => (
                      <TableRow key={r.name}>
                        <TableCell>{r.name}</TableCell>
                        <TableCell className='text-right tabular-nums'>{money(r.commit)}</TableCell>
                        <TableCell className='text-right tabular-nums'>{money(r.best)}</TableCell>
                        <TableCell className='text-right tabular-nums'>{money(r.pipeline)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            ) : (
              <EmptyNote title={`No calls submitted for ${quarter} yet.`}>
                AEs submit on Thursdays and the VP and CRO on Fridays through the forecast skill. Calls appear here from the Forecast Log tab.
              </EmptyNote>
            )}
            <EmptyNote title='Category changes this week'>
              Starts after the second weekly HubSpot snapshot, which lets us compare each deal&apos;s category with last week&apos;s.
            </EmptyNote>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
