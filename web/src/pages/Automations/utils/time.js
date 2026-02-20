const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto', style: 'narrow' });

const UNITS = [
  { unit: 'year', ms: 365.25 * 24 * 60 * 60 * 1000 },
  { unit: 'month', ms: 30.44 * 24 * 60 * 60 * 1000 },
  { unit: 'day', ms: 24 * 60 * 60 * 1000 },
  { unit: 'hour', ms: 60 * 60 * 1000 },
  { unit: 'minute', ms: 60 * 1000 },
  { unit: 'second', ms: 1000 },
];

export function formatRelativeTime(date) {
  if (!date) return '\u2014';
  const d = typeof date === 'string' ? new Date(date) : date;
  const diff = d.getTime() - Date.now();

  for (const { unit, ms } of UNITS) {
    const value = Math.round(diff / ms);
    if (Math.abs(value) >= 1 || unit === 'second') {
      return rtf.format(value, unit);
    }
  }
  return 'just now';
}

const dtf = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

export function formatDateTime(date) {
  if (!date) return '\u2014';
  const d = typeof date === 'string' ? new Date(date) : date;
  return dtf.format(d);
}

export function formatDuration(startDate, endDate) {
  if (!startDate || !endDate) return '\u2014';
  const start = typeof startDate === 'string' ? new Date(startDate) : startDate;
  const end = typeof endDate === 'string' ? new Date(endDate) : endDate;
  const ms = end.getTime() - start.getTime();

  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${Math.round(ms / 1000)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.round((ms % 60000) / 1000);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}
