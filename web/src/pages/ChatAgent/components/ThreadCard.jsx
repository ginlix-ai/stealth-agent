import React from 'react';
import { Trash2, Edit2 } from 'lucide-react';

/**
 * ThreadCard Component
 * 
 * Displays a single thread as a card with:
 * - Thread title or index as the name
 * - Status badge
 * - Edit icon that triggers rename modal
 * - Delete icon that triggers deletion confirmation
 * - Click handler to navigate to the thread conversation
 * 
 * @param {Object} thread - Thread object with thread_id, current_status, thread_index, title, etc.
 * @param {Function} onClick - Callback when card is clicked
 * @param {Function} onDelete - Callback when delete icon is clicked (receives thread)
 * @param {Function} onRename - Callback when edit icon is clicked (receives thread)
 */
function ThreadCard({ thread, onClick, onDelete, onRename }) {
  const handleDeleteClick = (e) => {
    e.stopPropagation(); // Prevent card click when clicking delete icon
    if (onDelete) {
      onDelete(thread);
    }
  };

  const handleRenameClick = (e) => {
    e.stopPropagation(); // Prevent card click when clicking edit icon
    if (onRename) {
      onRename(thread);
    }
  };
  return (
    <div
      className="group relative cursor-pointer transition-colors rounded-lg px-4 py-3 flex items-center gap-3 hover:bg-foreground/5"
      onClick={onClick}
      style={{
        borderBottom: '1px solid var(--color-border-muted)',
      }}
    >
      {/* Thread icon/indicator */}
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{
          backgroundColor: thread.current_status === 'completed'
            ? 'var(--color-profit)'
            : thread.current_status === 'in_progress'
            ? 'var(--color-accent-primary)'
            : 'var(--color-text-tertiary)',
        }}
      />

      {/* Thread title and info */}
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-normal truncate" style={{ color: 'var(--color-text-primary)' }}>
          {thread.title || `Thread ${thread.thread_index !== undefined ? thread.thread_index + 1 : ''}`}
        </h3>
        {thread.updated_at && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
            {new Date(thread.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </p>
        )}
      </div>

      {/* Action icons - Show on hover */}
      {(onRename || onDelete) && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {/* Edit/Rename icon */}
          {onRename && (
            <button
              onClick={handleRenameClick}
              className="p-1.5 rounded-md transition-colors hover:bg-foreground/10"
              style={{ color: 'var(--color-text-tertiary)' }}
              title="Rename thread"
            >
              <Edit2 className="h-3.5 w-3.5" />
            </button>
          )}
          {/* Delete icon */}
          {onDelete && (
            <button
              onClick={handleDeleteClick}
              className="p-1.5 rounded-md transition-colors hover:bg-[var(--color-danger-hover-bg)]"
              style={{ color: 'var(--color-loss)' }}
              title="Delete thread"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default ThreadCard;
