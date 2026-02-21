import React from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';

export default function StatusBadge({ status }) {
  const { t } = useTranslation();

  const STATUS_MAP = {
    active: { variant: 'success', label: t('automation.statusActive') },
    paused: { variant: 'warning', label: t('automation.statusPaused') },
    disabled: { variant: 'destructive', label: t('automation.statusDisabled') },
    completed: { variant: 'info', label: t('automation.statusCompleted') },
    failed: { variant: 'destructive', label: t('automation.statusFailed') },
    running: { variant: 'warning', label: t('automation.statusRunning') },
    pending: { variant: 'muted', label: t('automation.statusPending') },
  };

  const config = STATUS_MAP[status] || { variant: 'muted', label: status || t('automation.statusUnknown') };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
