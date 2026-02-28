import React from 'react';
import { Clock, Timer, CheckCircle2 } from 'lucide-react';
import { cronToHuman } from '../../../Automations/utils/cron';
import { formatRelativeTime } from '../../../Automations/utils/time';
import { useTranslation } from 'react-i18next';

// ─── Constants (matching InlineMarketCharts) ─────────────────────────

const GREEN = 'var(--color-profit)';
const YELLOW = 'var(--color-warning)';
const RED = 'var(--color-loss)';
const BLUE = 'var(--color-info)';
const TEXT_COLOR = 'var(--color-text-tertiary)';
const CARD_BG = 'var(--color-bg-elevated)';
const CARD_BORDER = 'var(--color-border-muted)';

const cardStyle = {
  background: CARD_BG,
  border: `1px solid ${CARD_BORDER}`,
  borderRadius: 8,
  padding: '12px 14px',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
};

// ─── Helpers ─────────────────────────────────────────────────────────

const STATUS_COLORS = {
  active: GREEN,
  paused: YELLOW,
  failed: RED,
  completed: BLUE,
  disabled: RED,
};

function statusColor(status) {
  return STATUS_COLORS[status] || TEXT_COLOR;
}

function scheduleLabel(automation) {
  if (!automation) return '';
  if (automation.trigger_type === 'cron' && automation.schedule) {
    return cronToHuman(automation.schedule);
  }
  if (automation.next_run_at) {
    return formatRelativeTime(automation.next_run_at);
  }
  return automation.schedule || '';
}

function StatusDot({ status }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        backgroundColor: statusColor(status),
        flexShrink: 0,
      }}
    />
  );
}

function QuoteRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
      <span style={{ opacity: 0.7 }}>{label}</span>
      <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ─── Router ──────────────────────────────────────────────────────────

export function InlineAutomationCard({ artifact, onClick }) {
  if (!artifact || artifact.type !== 'automations') return null;

  switch (artifact.mode) {
    case 'list':
      return <InlineAutomationListCard artifact={artifact} onClick={onClick} />;
    case 'detail':
      return <InlineAutomationDetailCard artifact={artifact} onClick={onClick} />;
    case 'created':
      return <InlineAutomationCreatedCard artifact={artifact} onClick={onClick} />;
    default:
      return null;
  }
}

// ─── List Card ───────────────────────────────────────────────────────

const MAX_INLINE = 4;

function InlineAutomationListCard({ artifact, onClick }) {
  const { t } = useTranslation();
  const { automations = [], total = 0 } = artifact;
  if (automations.length === 0) return null;

  const shown = automations.slice(0, MAX_INLINE);
  const remaining = total - shown.length;

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-default)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: 13 }}>{t('toolArtifact.automations')}</span>
        <span
          style={{
            fontSize: 11,
            color: TEXT_COLOR,
            backgroundColor: 'var(--color-bg-surface)',
            padding: '1px 6px',
            borderRadius: 10,
          }}
        >
          {total}
        </span>
      </div>

      {/* Rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {shown.map((a, i) => (
          <div
            key={a.automation_id || i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '3px 0',
              fontSize: 12,
            }}
          >
            <StatusDot status={a.status} />
            <span style={{ color: 'var(--color-text-primary)', fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {a.name}
            </span>
            <span style={{ color: TEXT_COLOR, flexShrink: 0, fontSize: 11 }}>
              {scheduleLabel(a)}
            </span>
          </div>
        ))}
      </div>

      {/* +N more */}
      {remaining > 0 && (
        <div style={{ marginTop: 4, fontSize: 11, color: TEXT_COLOR }}>
          {t('toolArtifact.nMoreAutomations', { count: remaining })}
        </div>
      )}
    </div>
  );
}

// ─── Detail Card ─────────────────────────────────────────────────────

function InlineAutomationDetailCard({ artifact, onClick }) {
  const { t } = useTranslation();
  const { automation, executions = [], total_executions = 0 } = artifact;
  if (!automation) return null;

  const isCron = automation.trigger_type === 'cron';
  const Icon = isCron ? Clock : Timer;

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-default)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      {/* Header: icon + name + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Icon size={14} style={{ color: TEXT_COLOR, flexShrink: 0 }} />
        <span style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 14, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {automation.name}
        </span>
        <span style={{ fontSize: 12, fontWeight: 500, color: statusColor(automation.status), flexShrink: 0 }}>
          {automation.status}
        </span>
      </div>

      {/* Key-value rows */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 20px', fontSize: 12, color: TEXT_COLOR }}>
        <QuoteRow label={t('toolArtifact.schedule')} value={scheduleLabel(automation)} />
        <QuoteRow label={t('toolArtifact.nextRun')} value={automation.next_run_at ? formatRelativeTime(automation.next_run_at) : '\u2014'} />
        {automation.last_run_at && (
          <QuoteRow label={t('toolArtifact.lastRun')} value={formatRelativeTime(automation.last_run_at)} />
        )}
        {total_executions > 0 && (
          <QuoteRow label={t('toolArtifact.executions')} value={t('toolArtifact.nTotal', { count: total_executions })} />
        )}
      </div>
    </div>
  );
}

// ─── Created Card ────────────────────────────────────────────────────

function InlineAutomationCreatedCard({ artifact, onClick }) {
  const { t } = useTranslation();
  if (!artifact) return null;

  return (
    <div
      style={{
        ...cardStyle,
        borderColor: 'var(--color-profit-border)',
      }}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-profit-border-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-profit-border)')}
    >
      {/* Header: checkmark + "Automation Created" */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <CheckCircle2 size={14} style={{ color: GREEN }} />
        <span style={{ fontWeight: 600, color: GREEN, fontSize: 13 }}>{t('toolArtifact.automationCreated')}</span>
      </div>

      {/* Name */}
      <div style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: 14, marginBottom: 8 }}>
        {artifact.name}
      </div>

      {/* Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 20px', fontSize: 12, color: TEXT_COLOR }}>
        <QuoteRow label={t('toolArtifact.schedule')} value={scheduleLabel(artifact)} />
        {artifact.next_run_at && (
          <QuoteRow label={t('toolArtifact.nextRun')} value={formatRelativeTime(artifact.next_run_at)} />
        )}
      </div>
    </div>
  );
}
