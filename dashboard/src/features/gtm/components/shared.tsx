'use client';

import * as React from 'react';
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { type ChartConfig, ChartStyle } from '@/components/ui/chart';
import { cn } from '@/lib/utils';
import type { Deal } from '@/lib/gtm/types';
import { type Grain, type Signal, formatDate, hubspotDealUrl, money, sum } from '@/lib/gtm/metrics';

/* Chart colors — validated for color-vision deficiency in light and dark (ordinal blue ramp for
   forecast certainty, blue/orange for deal type). */
export const categoryConfig = {
  COMMIT: { label: 'Commit', theme: { light: '#1c5cab', dark: '#86b6ef' } },
  BEST_CASE: { label: 'Best Case', theme: { light: '#3987e5', dark: '#3987e5' } },
  PIPELINE: { label: 'Pipeline', theme: { light: '#86b6ef', dark: '#1c5cab' } }
} satisfies ChartConfig;
export const typeConfig = {
  NB: { label: 'New Business', theme: { light: '#2a78d6', dark: '#3987e5' } },
  UP: { label: 'Upsell', theme: { light: '#eb6834', dark: '#d95926' } }
} satisfies ChartConfig;
export const WON_COLOR = { light: '#1baf7a', dark: '#199e70' };

/** Makes a chart config's colors (var(--color-KEY)) available to plain HTML children. */
export function ColorScope({ config, children, className }: { config: ChartConfig; children: React.ReactNode; className?: string }) {
  const id = `scope-${React.useId().replace(/:/g, '')}`;
  return (
    <div data-chart={id} className={className}>
      <ChartStyle id={id} config={config} />
      {children}
    </div>
  );
}

export function Section({
  id,
  title,
  description,
  controls,
  children
}: {
  id: string;
  title: string;
  description?: string;
  controls?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className='flex scroll-mt-24 flex-col gap-4'>
      <div className='flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b pb-3'>
        <div className='min-w-0'>
          <h2 id={`${id}-title`} className='text-xl font-semibold tracking-tight'>
            {title}
          </h2>
          {description && <p className='text-muted-foreground mt-1 max-w-prose text-sm'>{description}</p>}
        </div>
        {controls && <div className='flex flex-wrap items-center gap-2'>{controls}</div>}
      </div>
      {children}
    </section>
  );
}

export function KpiGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className='*:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card grid grid-cols-2 gap-3 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs lg:grid-cols-4'>
      {children}
    </div>
  );
}

export function Kpi({
  label,
  value,
  badge,
  footer,
  tone
}: {
  label: string;
  value: string;
  badge?: string;
  footer?: React.ReactNode;
  tone?: 'critical';
}) {
  return (
    <Card className='@container/card gap-2 py-4'>
      <CardHeader className='px-4'>
        <CardDescription>{label}</CardDescription>
        <CardTitle className='text-xl font-semibold tabular-nums @[220px]/card:text-2xl'>{value}</CardTitle>
        {badge && (
          <Badge variant='outline' className={cn('w-fit', tone === 'critical' && 'text-destructive')}>
            {badge}
          </Badge>
        )}
      </CardHeader>
      {footer && <CardFooter className='text-muted-foreground px-4 text-xs'>{footer}</CardFooter>}
    </Card>
  );
}

const GRAINS: { value: Grain; label: string }[] = [
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'year', label: 'Year' }
];
export function GrainToggle({ value, onChange }: { value: Grain; onChange: (g: Grain) => void }) {
  return (
    <ToggleGroup
      variant='outline'
      size='sm'
      spacing={0}
      aria-label='View by'
      value={[value]}
      onValueChange={(v) => v[0] && onChange(v[0] as Grain)}
    >
      {GRAINS.map((g) => (
        <ToggleGroupItem key={g.value} value={g.value}>
          {g.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

export function SimpleSelect<T extends string | number>({
  label,
  value,
  options,
  onChange,
  className
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  className?: string;
}) {
  const items = options.map((o) => ({ value: String(o.value), label: o.label }));
  return (
    <div className='flex items-center gap-2'>
      <span className='text-muted-foreground text-xs font-medium'>{label}</span>
      <Select
        items={items}
        value={String(value)}
        onValueChange={(v) => {
          const hit = options.find((o) => String(o.value) === v);
          if (hit) onChange(hit.value);
        }}
      >
        <SelectTrigger size='sm' className={cn('min-w-32', className)} aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {items.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

export function Legend({ config }: { config: ChartConfig }) {
  return (
    <div className='text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs'>
      {Object.entries(config).map(([k, c]) => (
        <span key={k} className='inline-flex items-center gap-1.5'>
          <span className='size-2.5 rounded-[3px]' style={{ background: `var(--color-${k})` }} />
          {c.label}
        </span>
      ))}
    </div>
  );
}

/** Horizontal bars for a breakdown (stage, owner). Segment colors come from the parent chart config. */
export function BreakdownBars<K extends string>({
  rows,
  order
}: {
  rows: { name: string; total: number; count: number; values: Partial<Record<K, number>> }[];
  order: K[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.total));
  if (!rows.length) return <p className='text-muted-foreground text-sm'>No deals match these filters.</p>;
  return (
    <ul className='flex flex-col gap-3'>
      {rows.map((r) => (
        <li key={r.name} className='grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 text-sm'>
          <span className='truncate' title={r.name}>
            {r.name}
          </span>
          <span className='text-muted-foreground tabular-nums'>
            {money(r.total)} · {r.count}
          </span>
          <span className='bg-muted col-span-2 flex h-2 gap-0.5 overflow-hidden rounded-full' aria-hidden>
            <span className='flex h-full gap-0.5' style={{ width: `${Math.max(2, (r.total / max) * 100)}%` }}>
              {order
                .filter((k) => r.values[k])
                .map((k) => (
                  <span key={k} className='h-full' style={{ flex: r.values[k], background: `var(--color-${k})` }} />
                ))}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Deal list shown under a chart when a bar is selected. */
export function DrillList({
  title,
  deals,
  portal,
  onClose
}: {
  title: string;
  deals: Deal[];
  portal: string;
  onClose: () => void;
}) {
  const sorted = [...deals].sort((a, b) => b.a - a.a);
  return (
    <div className='border-t pt-3'>
      <div className='mb-2 flex items-center justify-between gap-2 text-sm'>
        <span className='font-medium'>
          {title} · {deals.length} deal{deals.length === 1 ? '' : 's'} · {money(sum(deals))}
        </span>
        <Button variant='ghost' size='sm' onClick={onClose}>
          Clear
        </Button>
      </div>
      <div className='overflow-x-auto'>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Deal</TableHead>
              <TableHead className='hidden sm:table-cell'>Owner</TableHead>
              <TableHead className='hidden md:table-cell'>Stage</TableHead>
              <TableHead>Close</TableHead>
              <TableHead className='text-right'>Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((d) => (
              <TableRow key={d.id}>
                <TableCell className='max-w-56 truncate font-medium'>
                  <a href={hubspotDealUrl(portal, d.id)} target='_blank' rel='noopener noreferrer' className='hover:underline'>
                    {d.n}
                  </a>
                </TableCell>
                <TableCell className='hidden sm:table-cell'>{d.o}</TableCell>
                <TableCell className='hidden md:table-cell'>{d.st}</TableCell>
                <TableCell className='tabular-nums'>{formatDate(d.cd)}</TableCell>
                <TableCell className='text-right tabular-nums'>{money(d.a)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function SignalBadge({ s }: { s: Signal }) {
  return (
    <Badge
      variant={s.tone === 'critical' ? 'destructive' : 'outline'}
      className={cn(
        s.tone === 'warning' && 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
        s.tone === 'good' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
      )}
    >
      {s.label}
    </Badge>
  );
}

export function EmptyNote({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className='text-muted-foreground rounded-lg border border-dashed p-4 text-sm'>
      <p className='text-foreground font-medium'>{title}</p>
      <p className='mt-1'>{children}</p>
    </div>
  );
}
