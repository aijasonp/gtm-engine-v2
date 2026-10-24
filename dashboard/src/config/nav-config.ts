import { NavGroup } from '@/types';

/**
 * Sidebar + Cmd+K navigation. Add Marketing, CS, and Finance pages here as they're built.
 */
export const navGroups: NavGroup[] = [
  {
    label: 'Dashboards',
    items: [
      {
        title: 'GTM Snapshot',
        url: '/dashboard/gtm',
        icon: 'dashboard',
        isActive: false,
        shortcut: ['g', 'g'],
        items: []
      }
    ]
  }
];
