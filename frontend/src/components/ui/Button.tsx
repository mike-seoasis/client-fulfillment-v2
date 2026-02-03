'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-gold-500 text-warm-gray-900 hover:bg-gold-600 active:bg-gold-700 shadow-sm',
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

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', disabled, children, ...props }, ref) => {
    const baseClasses =
      'inline-flex items-center justify-center font-medium rounded-lg transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-gold-400 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

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

export { Button, type ButtonProps, type ButtonVariant, type ButtonSize };
