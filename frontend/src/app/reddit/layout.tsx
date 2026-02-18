'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const redditNavLinks = [
  { href: '/reddit', label: 'Projects', exact: true },
  { href: '/reddit/accounts', label: 'Accounts' },
  { href: '/reddit/comments', label: 'Comments' },
];

export default function RedditLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // Hide sub-nav on project detail pages (/reddit/[uuid])
  // UUID pattern: 8-4-4-4-12 hex chars
  const isDetailPage = /^\/reddit\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(pathname);

  if (isDetailPage) {
    return <div>{children}</div>;
  }

  return (
    <div>
      {/* Sub-navigation for Reddit section */}
      <div className="flex items-center gap-4 mb-6 border-b border-cream-300 pb-3">
        {redditNavLinks.map((link) => {
          const isActive = link.exact
            ? pathname === link.href
            : pathname === link.href || pathname.startsWith(link.href + '/');
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`text-sm font-medium pb-3 -mb-3 transition-colors duration-150 ${
                isActive
                  ? 'text-palm-700 border-b-2 border-palm-500'
                  : 'text-warm-gray-500 hover:text-warm-gray-700 border-b-2 border-transparent'
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
      {children}
    </div>
  );
}
