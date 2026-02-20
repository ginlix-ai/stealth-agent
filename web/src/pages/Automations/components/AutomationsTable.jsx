import React from 'react';
import { AnimatePresence } from 'framer-motion';
import AutomationRow from './AutomationRow';
import AutomationDetailOverlay from './AutomationDetailOverlay';
import EmptyState from './EmptyState';

export default function AutomationsTable({
  automations,
  loading,
  selectedAutomation,
  onSelectAutomation,
  onCloseOverlay,
  onCreateClick,
  onEdit,
  onDelete,
  onPause,
  onResume,
  onTrigger,
  mutationsLoading,
}) {
  if (!loading && automations.length === 0) {
    return <EmptyState onCreateClick={onCreateClick} />;
  }

  return (
    <div className="relative flex-1 min-h-0">
      {/* Column Headers */}
      <div
        className="grid grid-cols-[1fr_1fr_0.6fr_0.8fr_0.5fr] gap-4 px-4 py-2 text-xs uppercase tracking-wider mb-2"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        <span>Name</span>
        <span>Schedule</span>
        <span>Mode</span>
        <span>Next Run</span>
        <span className="text-right">Status</span>
      </div>

      {/* Rows */}
      <div className="flex flex-col gap-2">
        <AnimatePresence>
          {automations.map((automation, index) => (
            <AutomationRow
              key={automation.automation_id}
              automation={automation}
              index={index}
              onClick={onSelectAutomation}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Detail Overlay */}
      <AnimatePresence>
        {selectedAutomation && (
          <AutomationDetailOverlay
            automation={selectedAutomation}
            onClose={onCloseOverlay}
            onEdit={onEdit}
            onDelete={onDelete}
            onPause={onPause}
            onResume={onResume}
            onTrigger={onTrigger}
            mutationsLoading={mutationsLoading}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
