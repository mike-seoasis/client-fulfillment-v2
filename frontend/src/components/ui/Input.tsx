'use client';

import { forwardRef, type InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    const baseClasses =
      'block w-full px-4 py-2.5 text-warm-gray-900 bg-white border rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:bg-cream-100 disabled:cursor-not-allowed';

    const stateClasses = error
      ? 'border-coral-400 focus:border-coral-500 focus:ring-coral-300'
      : 'border-cream-400 hover:border-cream-500 focus:border-palm-400 focus:ring-palm-200';

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block mb-1.5 text-sm font-medium text-warm-gray-700"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`${baseClasses} ${stateClasses} ${className}`}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="mt-1.5 text-sm text-coral-600">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export { Input, type InputProps };
