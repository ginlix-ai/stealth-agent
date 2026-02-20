import React from 'react';
import { Badge } from '@/components/ui/badge';

const STATUS_MAP = {
  active: { variant: 'success', label: 'Active' },
  paused: { variant: 'warning', label: 'Paused' },
  disabled: { variant: 'destructive', label: 'Disabled' },
  completed: { variant: 'info', label: 'Completed' },
  failed: { variant: 'destructive', label: 'Failed' },
  running: { variant: 'warning', label: 'Running' },
  pending: { variant: 'muted', label: 'Pending' },
};

export default function StatusBadge({ status }) {
  const config = STATUS_MAP[status] || { variant: 'muted', label: status || 'Unknown' };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
