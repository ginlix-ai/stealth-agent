import React from 'react';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../../../components/ui/dialog';

/**
 * Reusable confirmation dialog. Uses color tokens only.
 */
function ConfirmDialog({ open, title, message, confirmLabel = 'Delete', onConfirm, onOpenChange }) {
  const handleConfirm = async () => {
    if (onConfirm) await onConfirm();
    onOpenChange?.(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-sm text-white border"
        style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}
      >
        <DialogHeader>
          <DialogTitle className="dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </DialogTitle>
          <p className="text-sm text-gray-400">{message}</p>
        </DialogHeader>
        <DialogFooter className="gap-2 pt-4">
          <button
            type="button"
            onClick={() => onOpenChange?.(false)}
            className="px-3 py-1.5 rounded text-sm border hover:bg-white/10"
            style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border-default)' }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="px-4 py-1.5 rounded text-sm font-medium hover:opacity-90"
            style={{ backgroundColor: 'var(--color-accent-primary)', color: 'var(--color-text-on-accent)' }}
          >
            {confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ConfirmDialog;
