'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { authClient } from '@/lib/auth/client';

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, isPending } = authClient.useSession();
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = [
    { href: '/', label: 'AI SEO', isActive: pathname === '/' || pathname.startsWith('/projects') },
    { href: '/reddit', label: 'Reddit', isActive: pathname.startsWith('/reddit') },
  ];

  const userName = session?.user?.name;
  const userEmail = session?.user?.email;
  const displayName = userName || userEmail || '';
  const avatarInitial = userName ? userName[0].toUpperCase() : userEmail ? userEmail[0].toUpperCase() : '?';

  const handleSignOut = async () => {
    await authClient.signOut({
      fetchOptions: {
        onSuccess: () => {
          router.push('/auth/sign-in');
        },
      },
    });
  };

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

          {/* User menu */}
          <div className="relative flex items-center">
            {isPending ? (
              /* Loading skeleton */
              <div className="flex items-center gap-2 px-3 py-2">
                <div className="h-8 w-8 rounded-full bg-cream-300 animate-pulse" />
                <div className="h-4 w-20 rounded bg-cream-300 animate-pulse" />
              </div>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="flex items-center gap-2 rounded-sm px-3 py-2 text-sm text-warm-gray-700 hover:bg-cream-200 transition-colors duration-150"
                >
                  <div className="h-8 w-8 rounded-full bg-cream-300 flex items-center justify-center text-warm-gray-600 font-medium">
                    {avatarInitial}
                  </div>
                  <span className="hidden sm:inline text-sm font-medium text-warm-gray-700 max-w-[150px] truncate">
                    {displayName}
                  </span>
                  <svg
                    className={`h-4 w-4 text-warm-gray-500 transition-transform duration-150 ${menuOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>

                {/* Dropdown menu */}
                {menuOpen && (
                  <>
                    {/* Backdrop to close menu */}
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setMenuOpen(false)}
                    />
                    <div className="absolute right-0 top-full mt-1 z-20 w-56 rounded-sm border border-sand-500 bg-white shadow-lg">
                      <div className="px-4 py-3 border-b border-cream-200">
                        <p className="text-sm font-medium text-warm-gray-900 truncate">
                          {userName || 'User'}
                        </p>
                        {userEmail && (
                          <p className="text-xs text-warm-gray-500 truncate">
                            {userEmail}
                          </p>
                        )}
                      </div>
                      <div className="py-1">
                        <button
                          type="button"
                          onClick={handleSignOut}
                          className="w-full px-4 py-2 text-left text-sm text-warm-gray-700 hover:bg-cream-100 transition-colors duration-150"
                        >
                          Sign out
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
