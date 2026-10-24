'use client';

import * as React from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import type { Deal, DealType } from '@/lib/gtm/types';
import {
  type Grain,
  bucketOf,
  bucketize,
  currentAndNext,
  cumulativeByMonth,
  fyLabel,
  isWon,
  money,
  parseDate,
  periodsFor,
  sum
} from '@/lib/gtm/metrics';
import { ColorScope, DrillList, GrainToggle, Kpi, KpiGrid, Legend, Section, SimpleSelect, typeConfig } from './shared';

export function BookingsSection({
  deals,
  asOf,
  portal,
  typeFilter
}: {
  deals: Deal[];
  asOf: Date;
  portal: string;
  typeFilter: 'all' | DealType;
}) {
  const curY = asOf.getUTCFullYear();
  const [grain, setGrain] = React.useState<Grain>('month');
  const [fy, setFy] = React.useState(curY);
  const [selected, setSelected] = React.useState<string | null>(null);

  const won = deals.filter(isWon);
  const years = [...new Set([...won.map((d) => parseDate(d.cd).getUTCFullYear()), curY])].sort();
  const series = (Object.keys(typeConfig) as DealType[]).filter((k) => typeFilter === 'all' || k === typeFilter);
  const shownConfig = Object.fromEntries(series.map((k) => [k, typeConfig[k]])) as ChartConfig;

  // FY-to-date vs. the same period last year
  const beforeCutoff = (d: Deal) => {
    const x = parseDate(d.cd);
    return x.getUTCMonth() * 100 + x.getUTCDate() <= asOf.getUTCMonth() * 100 + asOf.getUTCDate();
  };
  const isCur = fy === curY;
  const fyWon = won.filter((d) => parseDate(d.cd).getUTCFullYear() === fy);
  const thisPeriod = isCur ? fyWon.filter(beforeCutoff) : fyWon;
  const lastPeriod = won.filter((d) => parseDate(d.cd).getUTCFullYear() === fy - 1 && (!isCur || beforeCutoff(d)));
  const delta = sum(lastPeriod) ? (sum(thisPeriod) - sum(lastPeriod)) / sum(lastPeriod) : null;
  const { current: curPeriod } = currentAndNext(grain, asOf);
  const periodWon = won.filter((d) => curPeriod && bucketOf(parseDate(d.cd), grain).key === curPeriod.key);

  const { rows } = bucketize(won, grain, periodsFor(grain, grain === 'year' ? years : [fy]), (d) => d.t);
  const chartData = rows.map((r) => ({ key: r.key, label: r.label, title: r.title, ...r.values }));
  const sel = rows.find((r) => r.key === selected);

  const yoyYears = years.filter((y) => y <= curY);
  const yoyData = cumulativeByMonth(won, yoyYears, asOf);
  const yoyConfig = Object.fromEntries(
    yoyYears.map((y) => [
      fyLabel(y),
      { label: fyLabel(y), theme: y === fy ? { light: '#4f46e5', dark: '#8b83ff' } : { light: '#c4c2d4', dark: '#4a4660' } }
    ])
  ) as ChartConfig;

  return (
    <Section
      id='bookings'
      title='Bookings'
      description='Closed Won deals by close date, New Business and Upsell.'
      controls={
        <>
          <GrainToggle value={grain} onChange={(g) => { setGrain(g); setSelected(null); }} />
          {grain !== 'year' && (
            <SimpleSelect
              label='FY'
              value={fy}
              options={[...years].reverse().map((y) => ({ value: y, label: fyLabel(y) + (y === curY ? ' (current)' : '') }))}
              onChange={(v) => { setFy(v); setSelected(null); }}
            />
          )}
        </>
      }
    >
      <KpiGrid>
        <Kpi
          label={isCur ? `${fyLabel(fy)} to date` : `${fyLabel(fy)} total`}
          value={money(sum(thisPeriod))}
          footer={`${thisPeriod.length} deal${thisPeriod.length === 1 ? '' : 's'} · NB ${money(sum(thisPeriod.filter((d) => d.t === 'NB')))} · Upsell ${money(sum(thisPeriod.filter((d) => d.t === 'UP')))}`}
        />
        <Kpi
          label={`vs. ${fyLabel(fy - 1)}${isCur ? ' same period' : ''}`}
          value={delta === null ? '—' : `${delta >= 0 ? '+' : ''}${Math.round(delta * 100)}%`}
          footer={`${fyLabel(fy - 1)}: ${money(sum(lastPeriod))}`}
        />
        <Kpi label={`This ${grain} · ${curPeriod?.title ?? ''}`} value={money(sum(periodWon))} footer={`${periodWon.length} deal${periodWon.length === 1 ? '' : 's'} · ${grain} to date`} />
        <Kpi
          label={`Average deal · ${fyLabel(fy)}`}
          value={money(fyWon.length ? sum(fyWon) / fyWon.length : 0)}
          footer={fyWon.length ? `Largest ${money(Math.max(...fyWon.map((d) => d.a)))}` : 'No deals'}
        />
      </KpiGrid>

      <div className='grid grid-cols-1 items-start gap-4 xl:grid-cols-3'>
        <Card className='xl:col-span-2'>
          <CardHeader>
            <CardTitle>Bookings by {grain}</CardTitle>
            <CardDescription>{grain === 'year' ? 'All fiscal years' : fyLabel(fy)}</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <ChartContainer config={shownConfig} className='aspect-auto h-64 w-full'>
              <BarChart data={chartData} margin={{ left: 4, right: 4 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey='label' tickLine={false} axisLine={false} tickMargin={8} minTickGap={4} />
                <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={money} />
                <ChartTooltip
                  cursor={{ fillOpacity: 0.4 }}
                  content={
                    <ChartTooltipContent
                      labelFormatter={(_, p) => p?.[0]?.payload?.title}
                      formatter={(v, name) => (
                        <div className='flex w-full justify-between gap-4'>
                          <span className='text-muted-foreground'>{typeConfig[name as DealType]?.label}</span>
                          <span className='font-mono tabular-nums'>{money(Number(v))}</span>
                        </div>
                      )}
                    />
                  }
                />
                {series.map((k, i) => (
                  <Bar
                    key={k}
                    dataKey={k}
                    stackId='a'
                    fill={`var(--color-${k})`}
                    radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
                    className='cursor-pointer'
                    onClick={(e: { payload?: { key: string } }) => e.payload && setSelected((s) => (s === e.payload!.key ? null : e.payload!.key))}
                  />
                ))}
              </BarChart>
            </ChartContainer>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <ColorScope config={shownConfig}><Legend config={shownConfig} /></ColorScope>
              <span className='text-muted-foreground text-xs'>Select a bar to list its deals</span>
            </div>
            {sel && sel.count > 0 && (
              <DrillList title={`Booked ${sel.title}`} deals={sel.deals} portal={portal} onClose={() => setSelected(null)} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Year over year</CardTitle>
            <CardDescription>Cumulative bookings by month. {fyLabel(fy)} highlighted.</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={yoyConfig} className='aspect-auto h-64 w-full'>
              <LineChart data={yoyData} margin={{ left: 4, right: 12 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey='month' tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
                <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={money} />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      labelFormatter={(l) => `Through ${l}`}
                      formatter={(v, name) => (
                        <div className='flex w-full justify-between gap-4'>
                          <span className='text-muted-foreground'>{String(name)}</span>
                          <span className='font-mono tabular-nums'>{money(Number(v))}</span>
                        </div>
                      )}
                    />
                  }
                />
                {yoyYears.map((y) => (
                  <Line
                    key={y}
                    dataKey={fyLabel(y)}
                    type='monotone'
                    stroke={`var(--color-${fyLabel(y)})`}
                    strokeWidth={y === fy ? 2.5 : 1.5}
                    dot={false}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ChartContainer>
            <ColorScope config={yoyConfig} className='mt-3'><Legend config={yoyConfig} /></ColorScope>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
