import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, Timer, ExternalLink } from 'lucide-react';
import { cronToHuman } from '../../../Automations/utils/cron';
import { formatRelativeTime, formatDateTime, formatDuration } from '../../../Automations/utils/time';

// ─── Constants ───────────────────────────────────────────────────────

const GREEN = 'var(--color-profit)';
const YELLOW = 'var(--color-warning)';
const RED = 'var(--color-loss)';
const BLUE = 'var(--color-info)';
const TEXT_SECONDARY = 'var(--color-text-tertiary)';

const STATUS_COLORS = {
  active: GREEN,
  running: GREEN,
  paused: YELLOW,
  failed: RED,
  completed: BLUE,
  disabled: RED,
};

function statusColor(status) {
  return STATUS_COLORS[status] || TEXT_SECONDARY;
}

// ─── Shared sub-components ───────────────────────────────────────────

const STATUS_BG = {
  active: 'var(--color-profit-soft)',
  running: 'var(--color-profit-soft)',
  paused: 'var(--color-warning-soft)',
  failed: 'var(--color-loss-soft)',
  completed: 'var(--color-info-soft)',
  disabled: 'var(--color-loss-soft)',
};

function StatusBadge({ status }) {
  const color = statusColor(status);
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 10,
        backgroundColor: STATUS_BG[status] || 'var(--color-border-muted)',
        color,
        textTransform: 'capitalize',
      }}
    >
      {status}
    </span>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border-muted)',
        borderRadius: 8,
        padding: '8px 12px',
      }}
    >
      <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: TEXT_SECONDARY, marginBottom: 4 }}>
        {label}
      </p>
      <p style={{ fontSize: 14, color: 'var(--color-text-primary)', fontWeight: 500 }}>{value}</p>
      {sub && (
        <p style={{ fontSize: 11, color: TEXT_SECONDARY, marginTop: 2 }}>{sub}</p>
      )}
    </div>
  );
}

function ConfigRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 13 }}>
      <span style={{ color: TEXT_SECONDARY }}>{label}</span>
      <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function scheduleLabel(auto) {
  if (!auto) return '\u2014';
  if (auto.trigger_type === 'cron' && auto.schedule) return cronToHuman(auto.schedule);
  if (auto.next_run_at) return formatRelativeTime(auto.next_run_at);
  return auto.schedule || '\u2014';
}

const ACCENT = 'var(--color-accent-primary)';

function AutomationsPageLink({ automationId }) {
  const navigate = useNavigate();
  const path = automationId ? `/automations?id=${automationId}` : '/automations';
  return (
    <button
      onClick={() => navigate(path)}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors hover:bg-foreground/5"
      style={{ color: ACCENT, border: '1px solid var(--color-accent-soft)' }}
    >
      <ExternalLink size={14} />
      View in Automations
    </button>
  );
}

// ─── Router ──────────────────────────────────────────────────────────

export default function AutomationDetailPanel({ data }) {
  if (!data || data.type !== 'automations') return null;

  switch (data.mode) {
    case 'list':
      return <ListPanel automations={data.automations || []} total={data.total || 0} />;
    case 'detail':
      return <DetailPanel automation={data.automation} executions={data.executions || []} totalExecutions={data.total_executions || 0} />;
    case 'created':
      return <CreatedPanel data={data} />;
    default:
      return null;
  }
}

// ─── List Panel ──────────────────────────────────────────────────────

function ListPanel({ automations, total }) {
  if (automations.length === 0) {
    return (
      <div style={{ padding: 16, color: TEXT_SECONDARY, fontSize: 14 }}>
        No automations found.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p style={{ fontSize: 12, color: TEXT_SECONDARY }}>
        {total} automation{total !== 1 ? 's' : ''}
      </p>
      {automations.map((a, i) => {
        const isCron = a.trigger_type === 'cron';
        const Icon = isCron ? Clock : Timer;
        return (
          <div
            key={a.automation_id || i}
            style={{
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border-muted)',
              borderRadius: 8,
              padding: '10px 14px',
            }}
          >
            {/* Row 1: icon + name + status badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <Icon size={14} style={{ color: TEXT_SECONDARY, flexShrink: 0 }} />
              <span style={{ color: 'var(--color-text-primary)', fontWeight: 600, fontSize: 14, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a.name}
              </span>
              <StatusBadge status={a.status} />
            </div>
            {/* Row 2: schedule + next run + agent mode */}
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: TEXT_SECONDARY, flexWrap: 'wrap' }}>
              <span>{scheduleLabel(a)}</span>
              {a.next_run_at && (
                <span>Next: {formatRelativeTime(a.next_run_at)}</span>
              )}
              {a.agent_mode && (
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: '1px 6px',
                    borderRadius: 4,
                    backgroundColor: 'var(--color-bg-surface)',
                    color: 'var(--color-text-tertiary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.03em',
                  }}
                >
                  {a.agent_mode}
                </span>
              )}
            </div>
          </div>
        );
      })}
      <AutomationsPageLink />
    </div>
  );
}

// ─── Detail Panel ────────────────────────────────────────────────────

function DetailPanel({ automation, executions, totalExecutions }) {
  if (!automation) return null;

  const isCron = automation.trigger_type === 'cron';
  const Icon = isCron ? Clock : Timer;
  const schedule = isCron ? cronToHuman(automation.schedule) : 'One-time';
  const scheduleSub = isCron ? automation.schedule : null;

  return (
    <div className="space-y-4">
      {/* Header: icon + name + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon size={16} style={{ color: TEXT_SECONDARY, flexShrink: 0 }} />
        <span style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 16, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {automation.name}
        </span>
        <StatusBadge status={automation.status} />
      </div>

      {/* Stat grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <StatCard
          label="Schedule"
          value={schedule}
          sub={scheduleSub}
        />
        <StatCard
          label="Next Run"
          value={automation.next_run_at ? formatRelativeTime(automation.next_run_at) : '\u2014'}
          sub={automation.next_run_at ? formatDateTime(automation.next_run_at) : null}
        />
        <StatCard
          label="Last Run"
          value={automation.last_run_at ? formatRelativeTime(automation.last_run_at) : '\u2014'}
          sub={automation.last_run_at ? formatDateTime(automation.last_run_at) : null}
        />
      </div>

      {/* Instruction */}
      {automation.instruction && (
        <div>
          <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: TEXT_SECONDARY, marginBottom: 6 }}>
            Instruction
          </p>
          <div
            style={{
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 8,
              padding: '10px 12px',
              fontSize: 13,
              color: 'var(--color-text-tertiary)',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.5,
            }}
          >
            {automation.instruction}
          </div>
        </div>
      )}

      {/* Configuration */}
      <div>
        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: TEXT_SECONDARY, marginBottom: 6 }}>
          Configuration
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
          {automation.agent_mode && (
            <ConfigRow label="Agent Mode" value={automation.agent_mode.toUpperCase()} />
          )}
          <ConfigRow label="Trigger Type" value={isCron ? 'Recurring (cron)' : 'One-time'} />
        </div>
      </div>

      {/* Execution History */}
      {executions.length > 0 && (
        <div>
          <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: TEXT_SECONDARY, marginBottom: 6 }}>
            Execution History ({totalExecutions} total)
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {executions.map((e, i) => (
              <div
                key={e.execution_id || i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 10px',
                  fontSize: 12,
                  backgroundColor: 'var(--color-bg-surface)',
                  borderRadius: 6,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    backgroundColor: statusColor(e.status),
                    flexShrink: 0,
                  }}
                />
                <span style={{ color: 'var(--color-text-primary)', fontWeight: 500, flex: 1 }}>
                  {e.scheduled_at ? formatDateTime(e.scheduled_at) : 'Manual trigger'}
                </span>
                {e.started_at && e.completed_at && (
                  <span style={{ color: TEXT_SECONDARY, fontSize: 11 }}>
                    {formatDuration(e.started_at, e.completed_at)}
                  </span>
                )}
                {e.error_message && (
                  <span style={{ color: RED, fontSize: 11, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.error_message}>
                    {e.error_message}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <AutomationsPageLink automationId={automation.automation_id} />
    </div>
  );
}

// ─── Created Panel ───────────────────────────────────────────────────

function CreatedPanel({ data }) {
  const isCron = data.trigger_type === 'cron';
  const schedule = isCron ? cronToHuman(data.schedule) : 'One-time';

  return (
    <div className="space-y-4">
      {/* Confirmation header */}
      <div
        style={{
          backgroundColor: 'var(--color-profit-soft)',
          border: '1px solid var(--color-profit-border)',
          borderRadius: 8,
          padding: '12px 14px',
        }}
      >
        <p style={{ color: GREEN, fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
          Automation Created Successfully
        </p>
        <p style={{ color: 'var(--color-text-primary)', fontWeight: 600, fontSize: 16 }}>
          {data.name}
        </p>
      </div>

      {/* Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <StatCard label="Schedule" value={schedule} sub={isCron ? data.schedule : null} />
        <StatCard
          label="Next Run"
          value={data.next_run_at ? formatRelativeTime(data.next_run_at) : '\u2014'}
          sub={data.next_run_at ? formatDateTime(data.next_run_at) : null}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
        <ConfigRow label="Status" value={data.status || 'active'} />
        <ConfigRow label="Trigger Type" value={isCron ? 'Recurring' : 'One-time'} />
      </div>

      <AutomationsPageLink automationId={data.automation_id} />
    </div>
  );
}
