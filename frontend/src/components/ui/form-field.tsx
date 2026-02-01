/* eslint-disable react-refresh/only-export-components */
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Form field components with validation display
 *
 * These components follow the warm, sophisticated design system
 * with clear error states and helpful validation feedback.
 */

// ============================================================================
// Input Component
// ============================================================================

const inputVariants = cva(
  'w-full px-4 py-2.5 rounded-xl bg-white border text-warmgray-800 placeholder:text-warmgray-400 transition-all duration-200 ease-smooth focus:outline-none disabled:bg-cream-100 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        default:
          'border-cream-300 focus:border-primary-400 focus:ring-2 focus:ring-primary-100',
        error:
          'border-error-400 focus:border-error-500 focus:ring-2 focus:ring-error-100',
        success:
          'border-success-400 focus:border-success-500 focus:ring-2 focus:ring-success-100',
      },
      size: {
        default: 'h-11',
        sm: 'h-9 text-sm px-3 py-1.5',
        lg: 'h-12 text-lg px-5 py-3',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'>,
    VariantProps<typeof inputVariants> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, variant, size, type = 'text', ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(inputVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Input.displayName = 'Input'

// ============================================================================
// Textarea Component
// ============================================================================

const textareaVariants = cva(
  'w-full px-4 py-3 rounded-xl bg-white border text-warmgray-800 placeholder:text-warmgray-400 transition-all duration-200 ease-smooth focus:outline-none disabled:bg-cream-100 disabled:cursor-not-allowed resize-none',
  {
    variants: {
      variant: {
        default:
          'border-cream-300 focus:border-primary-400 focus:ring-2 focus:ring-primary-100',
        error:
          'border-error-400 focus:border-error-500 focus:ring-2 focus:ring-error-100',
        success:
          'border-success-400 focus:border-success-500 focus:ring-2 focus:ring-success-100',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement>,
    VariantProps<typeof textareaVariants> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <textarea
        className={cn(textareaVariants({ variant, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Textarea.displayName = 'Textarea'

// ============================================================================
// Select Component
// ============================================================================

const selectVariants = cva(
  'w-full px-4 py-2.5 rounded-xl bg-white border text-warmgray-800 transition-all duration-200 ease-smooth focus:outline-none disabled:bg-cream-100 disabled:cursor-not-allowed appearance-none bg-no-repeat cursor-pointer',
  {
    variants: {
      variant: {
        default:
          'border-cream-300 focus:border-primary-400 focus:ring-2 focus:ring-primary-100',
        error:
          'border-error-400 focus:border-error-500 focus:ring-2 focus:ring-error-100',
        success:
          'border-success-400 focus:border-success-500 focus:ring-2 focus:ring-success-100',
      },
      size: {
        default: 'h-11',
        sm: 'h-9 text-sm px-3',
        lg: 'h-12 text-lg px-5',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'>,
    VariantProps<typeof selectVariants> {}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, variant, size, children, ...props }, ref) => {
    return (
      <div className="relative">
        <select
          className={cn(
            selectVariants({ variant, size, className }),
            'pr-10',
          )}
          ref={ref}
          {...props}
        >
          {children}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
          <svg
            className="h-5 w-5 text-warmgray-400"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      </div>
    )
  },
)
Select.displayName = 'Select'

// ============================================================================
// Checkbox Component
// ============================================================================

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  error?: boolean
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const generatedId = React.useId()
    const inputId = id || generatedId

    return (
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          id={inputId}
          className={cn(
            'h-5 w-5 rounded-md border-2 bg-white transition-colors duration-200 ease-smooth cursor-pointer',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-cream-50',
            error
              ? 'border-error-400 text-error-500 focus:ring-error-200'
              : 'border-cream-400 text-primary-500 focus:ring-primary-200',
            'checked:bg-primary-500 checked:border-primary-500',
            'disabled:cursor-not-allowed disabled:opacity-50',
            className,
          )}
          ref={ref}
          {...props}
        />
        {label && (
          <label
            htmlFor={inputId}
            className={cn(
              'text-sm text-warmgray-700 cursor-pointer select-none',
              props.disabled && 'cursor-not-allowed opacity-50',
            )}
          >
            {label}
          </label>
        )}
      </div>
    )
  },
)
Checkbox.displayName = 'Checkbox'

// ============================================================================
// Label Component
// ============================================================================

export interface LabelProps
  extends React.LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean
  optional?: boolean
}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, children, required, optional, ...props }, ref) => {
    return (
      <label
        className={cn(
          'block text-sm font-medium text-warmgray-700 mb-1.5',
          className,
        )}
        ref={ref}
        {...props}
      >
        {children}
        {required && (
          <span className="text-error-500 ml-0.5" aria-hidden="true">
            *
          </span>
        )}
        {optional && (
          <span className="text-warmgray-400 font-normal ml-1.5">
            (optional)
          </span>
        )}
      </label>
    )
  },
)
Label.displayName = 'Label'

// ============================================================================
// HelperText Component
// ============================================================================

const helperTextVariants = cva('text-sm mt-1.5 flex items-start gap-1.5', {
  variants: {
    variant: {
      default: 'text-warmgray-500',
      error: 'text-error-600',
      success: 'text-success-600',
      warning: 'text-warning-600',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
})

export interface HelperTextProps
  extends React.HTMLAttributes<HTMLParagraphElement>,
    VariantProps<typeof helperTextVariants> {
  icon?: boolean
}

const HelperText = React.forwardRef<HTMLParagraphElement, HelperTextProps>(
  ({ className, variant, icon = false, children, ...props }, ref) => {
    return (
      <p
        className={cn(helperTextVariants({ variant, className }))}
        ref={ref}
        role={variant === 'error' ? 'alert' : undefined}
        {...props}
      >
        {icon && variant === 'error' && (
          <svg
            className="h-4 w-4 mt-0.5 flex-shrink-0"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
              clipRule="evenodd"
            />
          </svg>
        )}
        {icon && variant === 'success' && (
          <svg
            className="h-4 w-4 mt-0.5 flex-shrink-0"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z"
              clipRule="evenodd"
            />
          </svg>
        )}
        {icon && variant === 'warning' && (
          <svg
            className="h-4 w-4 mt-0.5 flex-shrink-0"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
              clipRule="evenodd"
            />
          </svg>
        )}
        {children}
      </p>
    )
  },
)
HelperText.displayName = 'HelperText'

// ============================================================================
// FormField Component (Composite)
// ============================================================================

export interface FormFieldProps {
  /** Field label */
  label?: string
  /** Mark field as required */
  required?: boolean
  /** Show optional indicator */
  optional?: boolean
  /** Error message to display */
  error?: string
  /** Success message to display */
  success?: string
  /** Helper text shown below input */
  helperText?: string
  /** Warning message */
  warning?: string
  /** Show icon in validation messages */
  showIcon?: boolean
  /** Additional class names for the wrapper */
  className?: string
  /** Child input element */
  children: React.ReactElement
  /** HTML id for the input (auto-generated if not provided) */
  id?: string
}

/**
 * FormField wraps form inputs with labels and validation feedback
 *
 * @example
 * <FormField label="Email" required error={errors.email}>
 *   <Input type="email" placeholder="you@example.com" />
 * </FormField>
 */
function FormField({
  label,
  required,
  optional,
  error,
  success,
  helperText,
  warning,
  showIcon = true,
  className,
  children,
  id,
}: FormFieldProps) {
  const generatedId = React.useId()
  const inputId = id || generatedId
  const errorId = `${inputId}-error`
  const helperId = `${inputId}-helper`

  // Determine the variant to pass to the child
  const variant = error ? 'error' : success ? 'success' : 'default'

  // Clone child with additional props
  const childWithProps = React.cloneElement(children, {
    id: inputId,
    variant,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error
      ? errorId
      : helperText || warning
        ? helperId
        : undefined,
    ...children.props,
  })

  return (
    <div className={cn('space-y-1', className)}>
      {label && (
        <Label htmlFor={inputId} required={required} optional={optional}>
          {label}
        </Label>
      )}
      {childWithProps}
      {error && (
        <HelperText id={errorId} variant="error" icon={showIcon}>
          {error}
        </HelperText>
      )}
      {!error && success && (
        <HelperText variant="success" icon={showIcon}>
          {success}
        </HelperText>
      )}
      {!error && !success && warning && (
        <HelperText id={helperId} variant="warning" icon={showIcon}>
          {warning}
        </HelperText>
      )}
      {!error && !success && !warning && helperText && (
        <HelperText id={helperId} variant="default">
          {helperText}
        </HelperText>
      )}
    </div>
  )
}
FormField.displayName = 'FormField'

// ============================================================================
// Exports
// ============================================================================

export {
  Input,
  inputVariants,
  Textarea,
  textareaVariants,
  Select,
  selectVariants,
  Checkbox,
  Label,
  HelperText,
  helperTextVariants,
  FormField,
}
