import React from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * DeleteConfirmModal Component
 * 
 * Confirmation dialog for deleting a workspace or thread.
 * 
 * @param {boolean} isOpen - Whether the modal is open
 * @param {string} workspaceName - Name of the workspace/thread to delete
 * @param {Function} onConfirm - Callback when user confirms deletion
 * @param {Function} onCancel - Callback when user cancels
 * @param {boolean} isDeleting - Whether deletion is in progress
 * @param {string} error - Error message to display (optional)
 * @param {string} itemType - Type of item being deleted ('workspace' or 'thread', defaults to 'workspace')
 */
function DeleteConfirmModal({ isOpen, workspaceName, onConfirm, onCancel, isDeleting, error, itemType = 'workspace' }) {
  const itemLabel = itemType === 'thread' ? 'thread' : 'workspace';
  const itemLabelCapitalized = itemType === 'thread' ? 'Thread' : 'Workspace';
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-bg-overlay-strong)' }}
      onClick={onCancel}
    >
      <div
        className="relative w-full max-w-md rounded-lg p-6"
        style={{
          backgroundColor: 'var(--color-bg-page)',
          border: '1px solid var(--color-border-muted)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Warning icon */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: 'rgba(255, 56, 60, 0.2)' }}
          >
            <AlertTriangle className="h-5 w-5" style={{ color: 'var(--color-loss)' }} />
          </div>
          <h2 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Delete {itemLabelCapitalized}
          </h2>
        </div>

        {/* Message */}
        <p className="text-sm mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Are you sure you want to delete the {itemLabel}
        </p>
        <p className="text-base font-medium mb-6" style={{ color: 'var(--color-text-primary)' }}>
          "{workspaceName}"?
        </p>
        <p className="text-xs mb-6" style={{ color: 'var(--color-loss)', opacity: 0.8 }}>
          This action cannot be undone. All data in this {itemLabel} will be permanently deleted.
        </p>

        {/* Error message */}
        {error && (
          <div className="mb-4 p-3 rounded-md" style={{ backgroundColor: 'rgba(255, 56, 60, 0.1)', border: '1px solid rgba(255, 56, 60, 0.3)' }}>
            <p className="text-sm" style={{ color: 'var(--color-loss)' }}>
              {error}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors hover:bg-foreground/10 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: isDeleting ? 'var(--color-loss-soft)' : 'var(--color-loss)',
              color: 'var(--color-text-on-accent)',
            }}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeleteConfirmModal;
