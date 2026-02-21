import React from 'react';
import { useTranslation } from 'react-i18next';
import { Clock } from 'lucide-react';

export default function EmptyState() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div
        className="rounded-full p-4"
        style={{ backgroundColor: 'var(--color-bg-elevated)' }}
      >
        <Clock className="w-8 h-8" style={{ color: 'var(--color-text-secondary)' }} />
      </div>
      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        {t('automation.noAutomationsYet')}
      </p>
    </div>
  );
}
