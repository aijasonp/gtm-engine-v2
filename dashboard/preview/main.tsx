import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { GtmSnapshot } from '@/features/gtm/components/gtm-snapshot';
import snapshot from '@/data/gtm-snapshot.json';
import type { Snapshot } from '@/lib/gtm/types';

// Preview shell only: follow the viewer's light/dark setting (the Next.js app uses next-themes).
function syncTheme() {
  const attr = document.documentElement.getAttribute('data-theme');
  const dark = attr ? attr === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.classList.toggle('dark', dark);
}
syncTheme();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncTheme);
new MutationObserver(syncTheme).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

function Shell() {
  return (
    <div className='bg-background text-foreground min-h-screen font-sans'>
      <div className='bg-background/60 sticky top-0 z-20 flex h-14 items-center gap-3 border-b px-4 backdrop-blur-md md:px-6'>
        <span className='bg-primary text-primary-foreground grid size-7 place-items-center rounded-md text-xs font-bold'>K</span>
        <span className='text-sm font-medium'>Dashboards</span>
        <span className='text-muted-foreground text-sm'>/ GTM Snapshot</span>
        <span className='text-muted-foreground ml-auto hidden text-xs sm:inline'>Prototype preview · snapshot data</span>
      </div>
      <GtmSnapshot snapshot={snapshot as Snapshot} />
    </div>
  );
}
createRoot(document.getElementById('root')!).render(<Shell />);
