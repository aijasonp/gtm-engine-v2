import type { Metadata } from 'next';
import { GtmSnapshot } from '@/features/gtm/components/gtm-snapshot';
import { getSnapshot } from '@/lib/gtm/data-source';

export const metadata: Metadata = { title: 'GTM Executive Snapshot' };

export default async function Page() {
  const snapshot = await getSnapshot();
  return <GtmSnapshot snapshot={snapshot} />;
}
