/**
 * DataTable component for displaying tabular data with sorting and filtering
 *
 * A warm, sophisticated table component for page listings.
 * Features:
 * - Sortable columns with visual indicators
 * - Optional search/filter functionality
 * - Row selection support
 * - Loading skeleton state
 * - Empty state handling
 * - Accessible keyboard navigation
 */

import { useState, useMemo, useCallback, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { addBreadcrumb } from '@/lib/errorReporting'

/** Sort direction options */
export type SortDirection = 'asc' | 'desc' | null

/** Column definition for the table */
export interface DataTableColumn<T> {
  /** Unique identifier for the column */
  id: string
  /** Header text to display */
  header: string
  /** Accessor function to get cell value from row data */
  accessor: (row: T) => ReactNode
  /** Whether this column is sortable */
  sortable?: boolean
  /** Custom sort function (optional, uses string comparison by default) */
  sortFn?: (a: T, b: T) => number
  /** Column width class (Tailwind) */
  width?: string
  /** Text alignment */
  align?: 'left' | 'center' | 'right'
  /** Optional cell className */
  cellClassName?: string
}

/** Sort state for the table */
export interface SortState {
  columnId: string | null
  direction: SortDirection
}

export interface DataTableProps<T> {
  /** Array of data rows to display */
  data: T[]
  /** Column definitions */
  columns: DataTableColumn<T>[]
  /** Function to get unique key for each row */
  getRowKey: (row: T) => string
  /** Whether to show loading skeleton */
  isLoading?: boolean
  /** Number of skeleton rows to show when loading */
  skeletonRowCount?: number
  /** Whether search/filter is enabled */
  searchable?: boolean
  /** Placeholder text for search input */
  searchPlaceholder?: string
  /** Function to filter data based on search query */
  searchFilter?: (row: T, query: string) => boolean
  /** Enable row selection */
  selectable?: boolean
  /** Selected row keys */
  selectedKeys?: Set<string>
  /** Callback when selection changes */
  onSelectionChange?: (selectedKeys: Set<string>) => void
  /** Callback when a row is clicked */
  onRowClick?: (row: T) => void
  /** Empty state message */
  emptyMessage?: string
  /** Empty state when search has no results */
  emptySearchMessage?: string
  /** Optional additional CSS classes */
  className?: string
}

/** Chevron icon for sort indicators */
function SortIcon({ direction }: { direction: SortDirection }) {
  if (direction === null) {
    return (
      <svg
        className="w-4 h-4 text-warmgray-300"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    )
  }

  return (
    <svg
      className={cn(
        'w-4 h-4 text-primary-500 transition-transform duration-200',
        direction === 'desc' && 'rotate-180'
      )}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
    </svg>
  )
}

/** Search icon */
function SearchIcon() {
  return (
    <svg
      className="w-5 h-5 text-warmgray-400"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  )
}

/** Checkbox component for row selection */
function Checkbox({
  checked,
  indeterminate,
  onChange,
  label,
}: {
  checked: boolean
  indeterminate?: boolean
  onChange: (checked: boolean) => void
  label: string
}) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        ref={(el) => {
          if (el) el.indeterminate = indeterminate || false
        }}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only peer"
        aria-label={label}
      />
      <div
        className={cn(
          'w-5 h-5 rounded-md border-2 transition-all duration-200',
          'flex items-center justify-center',
          checked || indeterminate
            ? 'bg-primary-500 border-primary-500'
            : 'bg-white border-cream-300 hover:border-cream-400'
        )}
      >
        {checked && !indeterminate && (
          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        )}
        {indeterminate && (
          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" />
          </svg>
        )}
      </div>
    </label>
  )
}

/**
 * DataTable component for displaying sortable, filterable tabular data
 */
export function DataTable<T>({
  data,
  columns,
  getRowKey,
  isLoading = false,
  skeletonRowCount = 5,
  searchable = false,
  searchPlaceholder = 'Search...',
  searchFilter,
  selectable = false,
  selectedKeys = new Set(),
  onSelectionChange,
  onRowClick,
  emptyMessage = 'No data available',
  emptySearchMessage = 'No results found',
  className,
}: DataTableProps<T>) {
  const [sortState, setSortState] = useState<SortState>({ columnId: null, direction: null })
  const [searchQuery, setSearchQuery] = useState('')

  // Handle column header click for sorting
  const handleSort = useCallback((column: DataTableColumn<T>) => {
    if (!column.sortable) return

    addBreadcrumb(`Sort column: ${column.header}`, 'user-action', {
      columnId: column.id,
      previousDirection: sortState.direction,
    })

    setSortState((prev) => {
      if (prev.columnId !== column.id) {
        return { columnId: column.id, direction: 'asc' }
      }
      if (prev.direction === 'asc') {
        return { columnId: column.id, direction: 'desc' }
      }
      return { columnId: null, direction: null }
    })
  }, [sortState.direction])

  // Handle search input change
  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
  }, [])

  // Handle select all checkbox
  const handleSelectAll = useCallback((checked: boolean) => {
    if (!onSelectionChange) return

    if (checked) {
      const allKeys = new Set(data.map(getRowKey))
      onSelectionChange(allKeys)
    } else {
      onSelectionChange(new Set())
    }
  }, [data, getRowKey, onSelectionChange])

  // Handle individual row selection
  const handleRowSelect = useCallback((row: T, checked: boolean) => {
    if (!onSelectionChange) return

    const key = getRowKey(row)
    const newSelected = new Set(selectedKeys)

    if (checked) {
      newSelected.add(key)
    } else {
      newSelected.delete(key)
    }

    onSelectionChange(newSelected)
  }, [getRowKey, onSelectionChange, selectedKeys])

  // Filter data based on search query
  const filteredData = useMemo(() => {
    if (!searchQuery || !searchFilter) return data
    return data.filter((row) => searchFilter(row, searchQuery.toLowerCase()))
  }, [data, searchQuery, searchFilter])

  // Sort filtered data
  const sortedData = useMemo(() => {
    if (!sortState.columnId || !sortState.direction) return filteredData

    const column = columns.find((c) => c.id === sortState.columnId)
    if (!column) return filteredData

    return [...filteredData].sort((a, b) => {
      let comparison: number

      if (column.sortFn) {
        comparison = column.sortFn(a, b)
      } else {
        const aValue = String(column.accessor(a) ?? '')
        const bValue = String(column.accessor(b) ?? '')
        comparison = aValue.localeCompare(bValue)
      }

      return sortState.direction === 'desc' ? -comparison : comparison
    })
  }, [filteredData, sortState, columns])

  // Calculate select all checkbox state
  const selectAllState = useMemo(() => {
    if (data.length === 0) return { checked: false, indeterminate: false }
    const selectedCount = data.filter((row) => selectedKeys.has(getRowKey(row))).length
    return {
      checked: selectedCount === data.length,
      indeterminate: selectedCount > 0 && selectedCount < data.length,
    }
  }, [data, selectedKeys, getRowKey])

  // Get alignment class
  const getAlignClass = (align?: 'left' | 'center' | 'right') => {
    switch (align) {
      case 'center': return 'text-center'
      case 'right': return 'text-right'
      default: return 'text-left'
    }
  }

  // Handle row click
  const handleRowClick = useCallback((row: T) => {
    if (onRowClick) {
      addBreadcrumb('Table row clicked', 'user-action', {
        rowKey: getRowKey(row),
      })
      onRowClick(row)
    }
  }, [onRowClick, getRowKey])

  // Handle row keyboard navigation
  const handleRowKeyDown = useCallback((e: React.KeyboardEvent, row: T) => {
    if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      handleRowClick(row)
    }
  }, [onRowClick, handleRowClick])

  return (
    <div className={cn('w-full', className)}>
      {/* Search bar */}
      {searchable && (
        <div className="mb-4">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <SearchIcon />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder={searchPlaceholder}
              className="input pl-10"
              aria-label="Search table"
            />
          </div>
        </div>
      )}

      {/* Table container */}
      <div className="bg-white rounded-2xl border border-cream-200 shadow-soft overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            {/* Table header */}
            <thead>
              <tr className="bg-cream-50 border-b border-cream-200">
                {/* Selection header */}
                {selectable && (
                  <th className="w-12 px-4 py-3">
                    <Checkbox
                      checked={selectAllState.checked}
                      indeterminate={selectAllState.indeterminate}
                      onChange={handleSelectAll}
                      label="Select all rows"
                    />
                  </th>
                )}
                {/* Column headers */}
                {columns.map((column) => (
                  <th
                    key={column.id}
                    className={cn(
                      'px-4 py-3 text-sm font-semibold text-warmgray-700',
                      getAlignClass(column.align),
                      column.width,
                      column.sortable && 'cursor-pointer select-none hover:bg-cream-100 transition-colors duration-150'
                    )}
                    onClick={() => handleSort(column)}
                    onKeyDown={(e) => {
                      if (column.sortable && (e.key === 'Enter' || e.key === ' ')) {
                        e.preventDefault()
                        handleSort(column)
                      }
                    }}
                    tabIndex={column.sortable ? 0 : undefined}
                    role={column.sortable ? 'button' : undefined}
                    aria-sort={
                      sortState.columnId === column.id
                        ? sortState.direction === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : undefined
                    }
                  >
                    <div className={cn(
                      'flex items-center gap-1.5',
                      column.align === 'center' && 'justify-center',
                      column.align === 'right' && 'justify-end'
                    )}>
                      <span>{column.header}</span>
                      {column.sortable && (
                        <SortIcon
                          direction={sortState.columnId === column.id ? sortState.direction : null}
                        />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            {/* Table body */}
            <tbody className="divide-y divide-cream-100">
              {/* Loading skeleton */}
              {isLoading && (
                <>
                  {Array.from({ length: skeletonRowCount }).map((_, index) => (
                    <tr key={`skeleton-${index}`} className="animate-pulse-soft">
                      {selectable && (
                        <td className="px-4 py-4">
                          <div className="w-5 h-5 bg-cream-200 rounded-md" />
                        </td>
                      )}
                      {columns.map((column) => (
                        <td key={column.id} className={cn('px-4 py-4', column.width)}>
                          <div className="h-5 bg-cream-200 rounded-lg w-3/4" />
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              )}

              {/* Empty state */}
              {!isLoading && sortedData.length === 0 && (
                <tr>
                  <td
                    colSpan={columns.length + (selectable ? 1 : 0)}
                    className="px-4 py-12 text-center"
                  >
                    <div className="text-warmgray-400">
                      <svg
                        className="w-12 h-12 mx-auto mb-4 text-cream-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                        />
                      </svg>
                      <p className="text-sm">
                        {searchQuery ? emptySearchMessage : emptyMessage}
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {/* Data rows */}
              {!isLoading && sortedData.map((row) => {
                const rowKey = getRowKey(row)
                const isSelected = selectedKeys.has(rowKey)

                return (
                  <tr
                    key={rowKey}
                    className={cn(
                      'transition-colors duration-150',
                      isSelected && 'bg-primary-50',
                      onRowClick && 'cursor-pointer hover:bg-cream-50',
                      !isSelected && !onRowClick && 'hover:bg-cream-50/50'
                    )}
                    onClick={() => handleRowClick(row)}
                    onKeyDown={(e) => handleRowKeyDown(e, row)}
                    tabIndex={onRowClick ? 0 : undefined}
                    role={onRowClick ? 'button' : undefined}
                    aria-selected={selectable ? isSelected : undefined}
                  >
                    {/* Selection checkbox */}
                    {selectable && (
                      <td
                        className="px-4 py-4"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Checkbox
                          checked={isSelected}
                          onChange={(checked) => handleRowSelect(row, checked)}
                          label={`Select row ${rowKey}`}
                        />
                      </td>
                    )}
                    {/* Data cells */}
                    {columns.map((column) => (
                      <td
                        key={column.id}
                        className={cn(
                          'px-4 py-4 text-sm text-warmgray-700',
                          getAlignClass(column.align),
                          column.width,
                          column.cellClassName
                        )}
                      >
                        {column.accessor(row)}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row count footer */}
      {!isLoading && data.length > 0 && (
        <div className="mt-3 text-xs text-warmgray-400 text-right">
          {searchQuery && filteredData.length !== data.length ? (
            <span>
              Showing {sortedData.length} of {data.length} items
            </span>
          ) : (
            <span>{data.length} items</span>
          )}
          {selectable && selectedKeys.size > 0 && (
            <span className="ml-2">• {selectedKeys.size} selected</span>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Loading skeleton for DataTable
 * Use when you need to show loading state before data structure is known
 */
export function DataTableSkeleton({
  columns = 4,
  rows = 5,
  showSearch = false,
  className,
}: {
  columns?: number
  rows?: number
  showSearch?: boolean
  className?: string
}) {
  return (
    <div className={cn('w-full', className)}>
      {/* Search skeleton */}
      {showSearch && (
        <div className="mb-4">
          <div className="h-11 bg-cream-200 rounded-xl animate-pulse-soft" />
        </div>
      )}

      {/* Table skeleton */}
      <div className="bg-white rounded-2xl border border-cream-200 shadow-soft overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-cream-50 border-b border-cream-200">
              {Array.from({ length: columns }).map((_, i) => (
                <th key={i} className="px-4 py-3">
                  <div className="h-5 bg-cream-200 rounded-lg w-24 animate-pulse-soft" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-cream-100">
            {Array.from({ length: rows }).map((_, rowIndex) => (
              <tr key={rowIndex}>
                {Array.from({ length: columns }).map((_, colIndex) => (
                  <td key={colIndex} className="px-4 py-4">
                    <div
                      className="h-5 bg-cream-200 rounded-lg animate-pulse-soft"
                      style={{ width: `${60 + Math.random() * 30}%` }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
