'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function Header() {
  const pathname = usePathname();

  const navLinks = [
    { href: '/', label: 'AI SEO', isActive: pathname === '/' || pathname.startsWith('/projects') },
    { href: '/reddit', label: 'Reddit', isActive: pathname.startsWith('/reddit') },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-cream-100 border-b border-cream-300">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo, title, and nav */}
          <div className="flex items-center gap-8">
            {/* Logo and title */}
            <div className="flex items-center gap-3">
              {/* Logo placeholder */}
              <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-palm-500 text-white font-bold text-lg">
                C
              </div>
              <span className="text-lg font-semibold text-warm-gray-900">
                Client Onboarding
              </span>
            </div>

            {/* Navigation links */}
            <nav className="flex items-center gap-6 h-16">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center h-full text-sm font-medium transition-colors duration-150 ${
                    link.isActive
                      ? 'text-palm-700 border-b-2 border-palm-500'
                      : 'text-warm-gray-500 hover:text-warm-gray-700 border-b-2 border-transparent'
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>

          {/* User menu placeholder */}
          <div className="flex items-center">
            <button
              type="button"
              className="flex items-center gap-2 rounded-sm px-3 py-2 text-sm text-warm-gray-700 hover:bg-cream-200 transition-colors duration-150"
            >
              <div className="h-8 w-8 rounded-full bg-cream-300 flex items-center justify-center text-warm-gray-600 font-medium">
                U
              </div>
              <svg
                className="h-4 w-4 text-warm-gray-500"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
