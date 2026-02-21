import React from 'react';
import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function AutomationsHeader({ automations, onCreateClick }) {
  const { t } = useTranslation();
  const activeCount = automations.filter((a) => a.status === 'active').length;
  const pausedCount = automations.filter((a) => a.status === 'paused').length;

  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: 'var(--color-profit)' }}
          />
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>{t('automation.automations')}</h1>
        </div>
        {automations.length > 0 && (
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {activeCount} {t('automation.active')}{pausedCount > 0 ? `, ${pausedCount} ${t('automation.paused')}` : ''}
          </span>
        )}
      </div>
      <Button
        onClick={onCreateClick}
        style={{ backgroundColor: 'var(--color-accent-primary)', color: 'var(--color-text-on-accent)' }}
      >
        <Plus className="w-4 h-4 mr-2" />
        {t('automation.createAutomation')}
      </Button>
    </div>
  );
}
