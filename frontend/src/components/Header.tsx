'use client';

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full bg-cream-100 border-b border-cream-300">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo and title */}
          <div className="flex items-center gap-3">
            {/* Logo placeholder */}
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-500 text-warm-gray-900 font-bold text-lg">
              C
            </div>
            <span className="text-lg font-semibold text-warm-gray-900">
              Client Onboarding
            </span>
          </div>

          {/* User menu placeholder */}
          <div className="flex items-center">
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-warm-gray-700 hover:bg-cream-200 transition-colors duration-150"
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
