'use client';

import * as React from 'react';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import type { Deal } from '@/lib/gtm/types';
import {
  type Grain,
  type PipeCategory,
  bucketize,
  bucketOf,
  currentAndNext,
  currentQuarter,
  weekFriday,
  fyLabel,
  groupBy,
  isPipeline,
  money,
  parseDate,
  periodsFor,
  pipeCategory,
  sum
} from '@/lib/gtm/metrics';
import {
  BreakdownBars,
  ColorScope,
  DrillList,
  GrainToggle,
  Kpi,
  KpiGrid,
  Legend,
  Section,
  SimpleSelect,
  categoryConfig
} from './shared';

const ORDER: PipeCategory[] = ['COMMIT', 'BEST_CASE', 'PIPELINE'];

export function PipelineSection({ deals, asOf, portal }: { deals: Deal[]; asOf: Date; portal: string }) {
  const cq = currentQuarter(asOf);
  const [grain, setGrain] = React.useState<Grain>('quarter');
  const [fromFy, setFromFy] = React.useState(cq.y);
  const [selected, setSelected] = React.useState<string | null>(null);

  const pipe = deals.filter(isPipeline);
  const pastDue = pipe.filter((d) => parseDate(d.cd) < asOf);
  // "This / next" follow the View-by toggle. Quarters and weeks use the forecast rule (this week's Friday).
  const { current, next } = currentAndNext(grain, grain === 'month' || grain === 'year' ? asOf : weekFriday(asOf));
  const inPeriod = (key?: string) => pipe.filter((d) => key !== undefined && bucketOf(parseDate(d.cd), grain).key === key);
  const inCur = inPeriod(current?.key);
  const inNext = inPeriod(next?.key);

  // Pipeline looks forward: month and quarter views show the chosen FY and the next one.
  const allYears = [...new Set(pipe.map((d) => parseDate(d.cd).getUTCFullYear()))].sort();
  const years =
    grain === 'year' ? allYears : grain === 'week' ? [fromFy] : [fromFy, fromFy + 1];
  const { rows, outside } = bucketize(pipe, grain, periodsFor(grain, years), (d) => pipeCategory(d.fc));
  const chartData = rows.map((r) => ({ key: r.key, label: r.label, title: r.title, ...r.values }));
  const inRange = rows.flatMap((r) => r.deals);
  const sel = rows.find((r) => r.key === selected);

  const byStage = groupBy(inRange, (d) => d.st, (d) => pipeCategory(d.fc))
    .map((g) => ({ ...g, so: g.deals[0].so }))
    .sort((a, b) => a.so - b.so);
  const byOwner = groupBy(inRange, (d) => d.o, (d) => pipeCategory(d.fc)).sort((a, b) => b.total - a.total);

  const fyOptions = [cq.y - 1, cq.y, cq.y + 1].map((y) => ({ value: y, label: fyLabel(y) + (y === cq.y ? ' (current)' : '') }));

  return (
    <Section
      id='pipeline'
      title='Pipeline'
      description="Open deals whose forecast category isn't Not Forecasted, by close date."
      controls={
        <>
          <GrainToggle value={grain} onChange={(g) => { setGrain(g); setSelected(null); }} />
          {grain !== 'year' && (
            <SimpleSelect label='From' value={fromFy} options={fyOptions} onChange={(v) => { setFromFy(v); setSelected(null); }} />
          )}
        </>
      }
    >
      <KpiGrid>
        <Kpi
          label={`Open pipeline · ${grain === 'year' ? 'all years' : years.map(fyLabel).join('–')}`}
          value={money(sum(inRange))}
          footer={`${inRange.length} deal${inRange.length === 1 ? '' : 's'} · ${money(sum(pipe))} open across all dates`}
        />
        <Kpi label={`This ${grain} · ${current?.title ?? ''}`} value={money(sum(inCur))} footer={`${inCur.length} deal${inCur.length === 1 ? '' : 's'} closing`} />
        <Kpi label={`Next ${grain} · ${next?.title ?? ''}`} value={money(sum(inNext))} footer={`${inNext.length} deal${inNext.length === 1 ? '' : 's'} closing`} />
        <Kpi
          label='Past close date'
          value={money(sum(pastDue))}
          footer={pastDue.length ? `${pastDue.length} open deals with a close date before today` : 'No open deals past their close date'}
          badge={pastDue.length ? 'Needs update' : undefined}
          tone='critical'
        />
      </KpiGrid>

      <div className='grid grid-cols-1 items-start gap-4 xl:grid-cols-3'>
        <Card className='xl:col-span-2'>
          <CardHeader>
            <CardTitle>Open pipeline by close {grain}</CardTitle>
            <CardDescription>
              {grain === 'year' ? 'All fiscal years' : years.map(fyLabel).join('–')}
              {outside.length > 0 && ` · ${outside.length} deal${outside.length === 1 ? '' : 's'} (${money(sum(outside))}) close outside this range`}
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-3'>
            <ChartContainer config={categoryConfig} className='aspect-auto h-64 w-full'>
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
                          <span className='text-muted-foreground'>{categoryConfig[name as PipeCategory]?.label}</span>
                          <span className='font-mono tabular-nums'>{money(Number(v))}</span>
                        </div>
                      )}
                    />
                  }
                />
                {ORDER.map((k, i) => (
                  <Bar
                    key={k}
                    dataKey={k}
                    stackId='a'
                    fill={`var(--color-${k})`}
                    radius={i === ORDER.length - 1 ? [4, 4, 0, 0] : 0}
                    className='cursor-pointer'
                    onClick={(e: { payload?: { key: string } }) => e.payload && setSelected((s) => (s === e.payload!.key ? null : e.payload!.key))}
                  />
                ))}
              </BarChart>
            </ChartContainer>
            <div className='flex flex-wrap items-center justify-between gap-2'>
              <ColorScope config={categoryConfig}><Legend config={categoryConfig} /></ColorScope>
              <span className='text-muted-foreground text-xs'>Select a bar to list its deals</span>
            </div>
            {sel && sel.count > 0 && (
              <DrillList title={`Closing ${sel.title}`} deals={sel.deals} portal={portal} onClose={() => setSelected(null)} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Breakdown</CardTitle>
            <CardDescription>Same range as the chart</CardDescription>
          </CardHeader>
          <CardContent>
            <ColorScope config={categoryConfig} className='flex flex-col gap-5'>
              <div>
                <h3 className='mb-2 text-sm font-medium'>By stage</h3>
                <BreakdownBars rows={byStage} order={ORDER} />
              </div>
              <div>
                <h3 className='mb-2 text-sm font-medium'>By owner</h3>
                <BreakdownBars rows={byOwner} order={ORDER} />
              </div>
            </ColorScope>
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
