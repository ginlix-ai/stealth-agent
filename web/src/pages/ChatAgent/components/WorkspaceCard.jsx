import React, { useState } from 'react';
import { Info, Trash2 } from 'lucide-react';
/**
 * WorkspaceCard Component
 * 
 * Displays a single workspace as a card with:
 * - Workspace name
 * - Info icon that shows description on click
 * - Delete icon that triggers deletion confirmation
 * - Click handler to navigate to the workspace chat
 * 
 * @param {Object} workspace - Workspace object with workspace_id, name, description, etc.
 * @param {Function} onClick - Callback when card is clicked
 * @param {Function} onDelete - Callback when delete icon is clicked (receives workspace)
 */
function WorkspaceCard({ workspace, onClick, onDelete }) {
  const [showDescription, setShowDescription] = useState(false);

  const handleInfoClick = (e) => {
    e.stopPropagation(); // Prevent card click when clicking info icon
    setShowDescription(!showDescription);
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation(); // Prevent card click when clicking delete icon
    if (onDelete) {
      onDelete(workspace);
    }
  };

  return (
    <div
      className="relative cursor-pointer transition-all hover:scale-105"
      onClick={onClick}
      style={{
        backgroundColor: 'var(--color-bg-card)',
        border: '1px solid var(--color-border-muted)',
        borderRadius: '8px',
        padding: '20px',
        minHeight: '120px',
      }}
    >
      {/* Action icons */}
      <div className="absolute top-3 right-3 flex items-center gap-1">
        {onDelete && (
          <button
            onClick={handleDeleteClick}
            className="p-1.5 rounded-full transition-colors hover:bg-[var(--color-danger-hover-bg)]"
            style={{ color: 'var(--color-loss)' }}
            title="Delete workspace"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
        {/* Info icon */}
        <button
          onClick={handleInfoClick}
          className="p-1.5 rounded-full transition-colors hover:bg-foreground/10"
          style={{ color: 'var(--color-accent-primary)' }}
          title="Show workspace info"
        >
          <Info className="h-4 w-4" />
        </button>
      </div>

      {/* Workspace name */}
      <h3 className="text-lg font-semibold pr-16" style={{ color: 'var(--color-text-primary)' }}>
        {workspace.name}
      </h3>

      {/* Info panel */}
      {showDescription && (
        <div
          className="absolute top-12 right-3 z-10 p-3 rounded-md shadow-lg max-w-xs"
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-muted)',
            color: 'var(--color-text-primary)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Workspace ID */}
          <div className="mb-2">
            <p className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>
              Workspace ID
            </p>
            <p className="text-xs font-mono break-all" style={{ color: 'var(--color-text-primary)' }}>
              {workspace.workspace_id}
            </p>
          </div>
          
          {/* Description */}
          {workspace.description && (
            <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--color-border-muted)' }}>
              <p className="text-xs mb-1" style={{ color: 'var(--color-text-tertiary)' }}>
                Description
              </p>
              <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                {workspace.description}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Status badge */}
      {workspace.status && (
        <div
          className="mt-3 inline-block px-2 py-1 rounded text-xs font-medium"
          style={{
            backgroundColor: workspace.status === 'running' ? 'var(--color-profit-soft)' : 'var(--color-border-muted)',
            color: workspace.status === 'running' ? 'var(--color-profit)' : 'var(--color-text-secondary)',
          }}
        >
          {workspace.status}
        </div>
      )}
    </div>
  );
}

export default WorkspaceCard;
