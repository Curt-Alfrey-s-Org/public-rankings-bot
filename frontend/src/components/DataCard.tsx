/**
 * Generic Data Card Component
 * Flexible card component for displaying various types of content
 * Can be used as a container for other components
 * 
 * @component
 * @example
 * <DataCard
 *   header="Player Stats"
 *   footer="Last updated: Jan 15"
 *   variant="highlight"
 * >
 *   <div>Custom content here</div>
 * </DataCard>
 */

import React from 'react'
import { X } from 'lucide-react'

interface DataCardProps {
  /** Card header/title */
  header?: string | React.ReactNode
  /** Card content (children) */
  children: React.ReactNode
  /** Card footer content */
  footer?: string | React.ReactNode
  /** Optional click handler */
  onClick?: () => void
  /** Optional close handler */
  onClose?: () => void
  /** Visual variant */
  variant?: 'default' | 'highlight' | 'danger'
  /** Optional CSS class */
  className?: string
  /** Whether the card is loading */
  isLoading?: boolean
  /** Whether to show hover effects */
  interactive?: boolean
}

const getVariantColor = (variant?: string): string => {
  switch (variant) {
    case 'highlight':
      return 'bg-slate-900/80 border-sky-500/30 hover:border-sky-500/50'
    case 'danger':
      return 'bg-slate-900/60 border-red-500/30 hover:border-red-500/50'
    default:
      return 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
  }
}

export default function DataCard({
  header,
  children,
  footer,
  onClick,
  onClose,
  variant = 'default',
  className = '',
  isLoading = false,
  interactive = !!onClick,
}: DataCardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        border rounded-lg transition-all duration-200
        ${getVariantColor(variant)}
        ${interactive ? 'cursor-pointer' : ''}
        ${className}
      `}
      role={interactive ? 'button' : 'article'}
      aria-busy={isLoading}
    >
      {/* Header */}
      {header && (
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-800/50 flex items-center justify-between gap-3">
          <div className="flex-1 min-w-0">
            {typeof header === 'string' ? (
              <h3 className="text-sm sm:text-base font-semibold text-white truncate">
                {header}
              </h3>
            ) : (
              header
            )}
          </div>
          {onClose && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onClose()
              }}
              className="p-1 hover:bg-slate-800 rounded transition-colors flex-shrink-0"
              aria-label="Close"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="px-4 sm:px-6 py-4 sm:py-5">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-4 h-4 border-2 border-sky-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          children
        )}
      </div>

      {/* Footer */}
      {footer && (
        <div className="px-4 sm:px-6 py-3 border-t border-slate-800/50 bg-slate-900/30">
          {typeof footer === 'string' ? (
            <p className="text-xs sm:text-sm text-slate-400">{footer}</p>
          ) : (
            footer
          )}
        </div>
      )}
    </div>
  )
}
