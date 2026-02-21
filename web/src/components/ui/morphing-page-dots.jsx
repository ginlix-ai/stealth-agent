import React from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * MorphingPageDots — controlled pagination dots with morphing animation.
 *
 * @param {number}   totalPages   Total number of pages
 * @param {number}   activeIndex  Currently active page (0-indexed)
 * @param {Function} onChange     Called with new page index when user navigates
 */
function MorphingPageDots({ totalPages, activeIndex, onChange }) {
  if (totalPages <= 1) return null;

  // For many pages, only show a window of dots around the active page
  const maxVisible = 7;
  let startPage = 0;
  let endPage = totalPages;

  if (totalPages > maxVisible) {
    const half = Math.floor(maxVisible / 2);
    startPage = Math.max(0, activeIndex - half);
    endPage = startPage + maxVisible;
    if (endPage > totalPages) {
      endPage = totalPages;
      startPage = endPage - maxVisible;
    }
  }

  const visiblePages = [];
  for (let i = startPage; i < endPage; i++) {
    visiblePages.push(i);
  }

  return (
    <div className="flex items-center justify-center gap-2 py-4">
      {/* Previous arrow */}
      <button
        onClick={() => onChange(Math.max(0, activeIndex - 1))}
        disabled={activeIndex === 0}
        className="p-1 rounded-md transition-colors hover:bg-foreground/10 disabled:opacity-20 disabled:cursor-not-allowed"
        style={{ color: 'var(--color-text-primary)' }}
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      {/* Dots */}
      <div className="flex items-center gap-1.5">
        {startPage > 0 && (
          <span className="text-xs px-1" style={{ color: 'var(--color-icon-muted)' }}>...</span>
        )}
        {visiblePages.map((pageIndex) => {
          const isActive = pageIndex === activeIndex;
          return (
            <motion.button
              key={pageIndex}
              onClick={() => onChange(pageIndex)}
              className="rounded-full transition-colors"
              style={{
                backgroundColor: isActive ? 'var(--color-accent-primary)' : 'var(--color-border-muted)',
              }}
              animate={{
                width: isActive ? 24 : 8,
                height: 8,
              }}
              transition={{
                type: 'spring',
                stiffness: 380,
                damping: 30,
              }}
              aria-label={`Go to page ${pageIndex + 1}`}
              aria-current={isActive ? 'page' : undefined}
            />
          );
        })}
        {endPage < totalPages && (
          <span className="text-xs px-1" style={{ color: 'var(--color-icon-muted)' }}>...</span>
        )}
      </div>

      {/* Next arrow */}
      <button
        onClick={() => onChange(Math.min(totalPages - 1, activeIndex + 1))}
        disabled={activeIndex === totalPages - 1}
        className="p-1 rounded-md transition-colors hover:bg-foreground/10 disabled:opacity-20 disabled:cursor-not-allowed"
        style={{ color: 'var(--color-text-primary)' }}
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}

export default MorphingPageDots;
