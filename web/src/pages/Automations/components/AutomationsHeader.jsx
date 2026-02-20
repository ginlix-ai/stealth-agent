import React from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function AutomationsHeader({ automations, onCreateClick }) {
  const activeCount = automations.filter((a) => a.status === 'active').length;
  const pausedCount = automations.filter((a) => a.status === 'paused').length;

  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: '#22c55e' }}
          />
          <h1 className="text-xl font-semibold text-white">Automations</h1>
        </div>
        {automations.length > 0 && (
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {activeCount} active{pausedCount > 0 ? `, ${pausedCount} paused` : ''}
          </span>
        )}
      </div>
      <Button
        onClick={onCreateClick}
        className="text-white"
        style={{ backgroundColor: '#6155F5' }}
      >
        <Plus className="w-4 h-4 mr-2" />
        Create Automation
      </Button>
    </div>
  );
}
