'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import Link from 'next/link';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-palm-500 text-white hover:bg-palm-600 active:bg-palm-700 shadow-sm',
  secondary:
    'bg-cream-200 text-warm-gray-800 hover:bg-cream-300 active:bg-cream-400 shadow-sm',
  danger:
    'bg-coral-500 text-white hover:bg-coral-600 active:bg-coral-700 shadow-sm',
  ghost:
    'bg-transparent text-warm-gray-700 hover:bg-cream-200 active:bg-cream-300',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

const baseClasses =
  'inline-flex items-center justify-center font-medium rounded-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

/**
 * A Next.js Link styled as a button. Use this instead of nesting
 * <Button> inside <Link>, which creates invalid HTML (<button> inside <a>)
 * and causes rendering bugs in Next.js production builds.
 */
interface ButtonLinkProps {
  href: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children: React.ReactNode;
}

function ButtonLink({
  href,
  variant = 'primary',
  size = 'md',
  className = '',
  children,
}: ButtonLinkProps) {
  return (
    <Link
      href={href}
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
    >
      {children}
    </Link>
  );
}

export { Button, ButtonLink, type ButtonProps, type ButtonLinkProps, type ButtonVariant, type ButtonSize };
