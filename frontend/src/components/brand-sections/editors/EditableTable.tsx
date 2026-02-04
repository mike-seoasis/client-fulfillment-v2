'use client';

import { useState, useCallback, useRef, useEffect, type KeyboardEvent } from 'react';

/**
 * Column schema for the editable table.
 * Defines the structure and display of each column.
 */
export interface ColumnSchema {
  /** Unique key for this column (matches object property name) */
  key: string;
  /** Display header for the column */
  header: string;
  /** Optional placeholder text for empty cells */
  placeholder?: string;
  /** Column width class (Tailwind) */
  width?: string;
  /** Whether this column is required */
  required?: boolean;
}

interface EditableTableProps {
  /** Current array of row objects */
  value: Record<string, string>[];
  /** Called when rows change */
  onChange: (rows: Record<string, string>[]) => void;
  /** Column definitions */
  columns: ColumnSchema[];
  /** Whether the table is disabled */
  disabled?: boolean;
  /** Optional label */
  label?: string;
  /** Placeholder text for "add row" button */
  addButtonText?: string;
  /** Minimum rows to maintain (defaults to 0) */
  minRows?: number;
}

interface EditingCell {
  rowIndex: number;
  columnKey: string;
}

/**
 * Editable table component for tabular data editing.
 * Supports dynamic columns via schema, add/delete rows, and inline cell editing.
 * Styled with tropical oasis palette.
 */
export function EditableTable({
  value,
  onChange,
  columns,
  disabled = false,
  label,
  addButtonText = 'Add row',
  minRows = 0,
}: EditableTableProps) {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when entering edit mode
  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingCell]);

  const handleCellClick = useCallback(
    (rowIndex: number, columnKey: string) => {
      if (disabled) return;
      const currentValue = value[rowIndex]?.[columnKey] || '';
      setEditValue(currentValue);
      setEditingCell({ rowIndex, columnKey });
    },
    [disabled, value]
  );

  const handleSaveCell = useCallback(() => {
    if (!editingCell) return;

    const { rowIndex, columnKey } = editingCell;
    const newRows = [...value];
    newRows[rowIndex] = {
      ...newRows[rowIndex],
      [columnKey]: editValue.trim(),
    };
    onChange(newRows);
    setEditingCell(null);
  }, [editingCell, editValue, value, onChange]);

  const handleCancelEdit = useCallback(() => {
    setEditingCell(null);
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSaveCell();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCancelEdit();
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        handleSaveCell();
        // Move to next cell
        if (editingCell) {
          const currentColIndex = columns.findIndex((c) => c.key === editingCell.columnKey);
          const nextColIndex = currentColIndex + 1;
          if (nextColIndex < columns.length) {
            // Move to next column in same row
            handleCellClick(editingCell.rowIndex, columns[nextColIndex].key);
          } else if (editingCell.rowIndex + 1 < value.length) {
            // Move to first column in next row
            handleCellClick(editingCell.rowIndex + 1, columns[0].key);
          }
        }
      }
    },
    [handleSaveCell, handleCancelEdit, editingCell, columns, value.length, handleCellClick]
  );

  const handleAddRow = useCallback(() => {
    if (disabled) return;
    // Create empty row with all column keys
    const newRow: Record<string, string> = {};
    columns.forEach((col) => {
      newRow[col.key] = '';
    });
    const newRows = [...value, newRow];
    onChange(newRows);
    // Start editing first cell of new row
    setTimeout(() => {
      handleCellClick(newRows.length - 1, columns[0].key);
    }, 0);
  }, [disabled, columns, value, onChange, handleCellClick]);

  const handleDeleteRow = useCallback(
    (rowIndex: number) => {
      if (disabled) return;
      if (value.length <= minRows) return;
      const newRows = value.filter((_, index) => index !== rowIndex);
      onChange(newRows);
      // Clear editing if we deleted the editing row
      if (editingCell?.rowIndex === rowIndex) {
        setEditingCell(null);
      }
    },
    [disabled, value, minRows, onChange, editingCell]
  );

  const isEditing = (rowIndex: number, columnKey: string) =>
    editingCell?.rowIndex === rowIndex && editingCell?.columnKey === columnKey;

  return (
    <div className="w-full">
      {label && (
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">{label}</label>
      )}

      <div className="border border-cream-400 rounded-sm overflow-hidden">
        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-cream-100 border-b border-cream-300">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`text-left py-2.5 px-3 text-warm-gray-600 font-medium ${col.width || ''}`}
                  >
                    {col.header}
                    {col.required && <span className="text-coral-500 ml-0.5">*</span>}
                  </th>
                ))}
                {!disabled && <th className="w-10 py-2.5 px-2" aria-label="Actions" />}
              </tr>
            </thead>
            <tbody>
              {value.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length + (disabled ? 0 : 1)}
                    className="py-8 text-center text-warm-gray-400 text-sm"
                  >
                    No rows yet. Click &quot;{addButtonText}&quot; to add one.
                  </td>
                </tr>
              ) : (
                value.map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className="border-b border-cream-200 last:border-b-0 hover:bg-cream-50 transition-colors duration-100"
                  >
                    {columns.map((col) => (
                      <td key={col.key} className="py-0 px-0">
                        {isEditing(rowIndex, col.key) ? (
                          <input
                            ref={inputRef}
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={handleSaveCell}
                            onKeyDown={handleKeyDown}
                            placeholder={col.placeholder}
                            data-editable-cell="true"
                            className="w-full py-2 px-3 text-sm text-warm-gray-900 bg-white border-2 border-palm-400 outline-none"
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleCellClick(rowIndex, col.key)}
                            disabled={disabled}
                            className={`
                              w-full text-left py-2 px-3 min-h-[40px]
                              ${disabled ? 'cursor-default' : 'cursor-text hover:bg-cream-100'}
                              ${row[col.key] ? 'text-warm-gray-800' : 'text-warm-gray-400'}
                              transition-colors duration-100
                            `}
                          >
                            {row[col.key] || col.placeholder || '—'}
                          </button>
                        )}
                      </td>
                    ))}
                    {!disabled && (
                      <td className="py-2 px-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleDeleteRow(rowIndex)}
                          disabled={value.length <= minRows}
                          className={`
                            p-1.5 rounded-sm transition-colors duration-150
                            focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                            ${
                              value.length <= minRows
                                ? 'text-warm-gray-300 cursor-not-allowed'
                                : 'text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50'
                            }
                          `}
                          aria-label={`Delete row ${rowIndex + 1}`}
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        </button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Add Row Button */}
        {!disabled && (
          <div className="border-t border-cream-300 bg-cream-50 px-3 py-2">
            <button
              type="button"
              onClick={handleAddRow}
              className="
                inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                text-palm-600 hover:text-palm-700 hover:bg-palm-50
                rounded-sm transition-colors duration-150
                focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
              "
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              {addButtonText}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export type { EditableTableProps };
