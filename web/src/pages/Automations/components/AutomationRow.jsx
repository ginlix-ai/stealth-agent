import React from 'react';
import { motion } from 'framer-motion';
import { Clock, Timer } from 'lucide-react';
import StatusBadge from './StatusBadge';
import { cronToHuman } from '../utils/cron';
import { formatRelativeTime, formatDateTime } from '../utils/time';

const STATUS_GLOW = {
  active: 'var(--color-success-soft)',
  paused: 'var(--color-warning-soft)',
  disabled: 'var(--color-loss-soft)',
  completed: 'var(--color-info-soft)',
};

export default function AutomationRow({ automation, index, onClick }) {
  const isCron = automation.trigger_type === 'cron';
  const schedule = isCron
    ? cronToHuman(automation.cron_expression)
    : formatDateTime(automation.next_run_at);

  const glowColor = STATUS_GLOW[automation.status] || 'transparent';

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      whileHover={{ y: -1 }}
      onClick={() => onClick(automation)}
      className="grid grid-cols-[1fr_1fr_0.6fr_0.8fr_0.5fr] gap-4 items-center px-4 py-3 cursor-pointer transition-colors relative overflow-hidden rounded-lg border"
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderColor: 'var(--color-border-default)',
      }}
    >
      {/* Status gradient glow on right edge */}
      <div
        className="absolute inset-y-0 right-0 w-32 pointer-events-none"
        style={{
          background: `linear-gradient(to left, ${glowColor}, transparent)`,
        }}
      />

      {/* Name */}
      <div className="flex items-center gap-2 min-w-0">
        {isCron ? (
          <Clock className="w-4 h-4 shrink-0" style={{ color: 'var(--color-text-secondary)' }} />
        ) : (
          <Timer className="w-4 h-4 shrink-0" style={{ color: 'var(--color-text-secondary)' }} />
        )}
        <span className="text-sm truncate font-medium" style={{ color: 'var(--color-text-primary)' }}>{automation.name}</span>
      </div>

      {/* Schedule */}
      <span className="text-sm truncate" style={{ color: 'var(--color-text-secondary)' }}>
        {schedule}
      </span>

      {/* Agent Mode */}
      <span
        className="text-xs uppercase font-mono tracking-wide"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {automation.agent_mode}
      </span>

      {/* Next Run */}
      <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        {automation.next_run_at ? formatRelativeTime(automation.next_run_at) : '\u2014'}
      </span>

      {/* Status */}
      <div className="flex justify-end relative z-10">
        <StatusBadge status={automation.status} />
      </div>
    </motion.div>
  );
}
