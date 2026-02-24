'use client';

import { forwardRef, type HTMLAttributes, type MouseEventHandler } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  onClick?: MouseEventHandler<HTMLDivElement>;
  hoverable?: boolean;
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ onClick, hoverable, className = '', children, ...props }, ref) => {
    const isClickable = !!onClick || hoverable;

    const baseClasses =
      'bg-white rounded-sm border border-cream-500 shadow transition-all duration-150';

    const interactiveClasses = isClickable
      ? 'cursor-pointer hover:shadow-md hover:border-cream-400 hover:-translate-y-0.5 active:translate-y-0 active:shadow-sm'
      : '';

    return (
      <div
        ref={ref}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={onClick}
        onKeyDown={
          onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onClick(e as unknown as React.MouseEvent<HTMLDivElement>);
                }
              }
            : undefined
        }
        className={`${baseClasses} ${interactiveClasses} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export { Card, type CardProps };
