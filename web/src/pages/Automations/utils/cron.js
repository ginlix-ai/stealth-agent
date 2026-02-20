const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function formatHour(h) {
  const hour = parseInt(h, 10);
  if (hour === 0) return '12:00 AM';
  if (hour < 12) return `${hour}:00 AM`;
  if (hour === 12) return '12:00 PM';
  return `${hour - 12}:00 PM`;
}

function formatMinuteHour(min, hour) {
  const h = parseInt(hour, 10);
  const m = parseInt(min, 10).toString().padStart(2, '0');
  if (h === 0) return `12:${m} AM`;
  if (h < 12) return `${h}:${m} AM`;
  if (h === 12) return `12:${m} PM`;
  return `${h - 12}:${m} PM`;
}

function parseDayRange(dayField) {
  if (dayField === '1-5') return 'Mon\u2013Fri';
  if (dayField === '0,6' || dayField === '6,0') return 'Sat\u2013Sun';
  const parts = dayField.split(',');
  if (parts.every((p) => /^\d$/.test(p))) {
    return parts.map((d) => DAYS[parseInt(d, 10)] || d).join(', ');
  }
  return dayField;
}

export function cronToHuman(expression) {
  if (!expression) return '';

  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) return expression;

  const [min, hour, dom, mon, dow] = parts;

  // Every N minutes: */N * * * *
  if (min.startsWith('*/') && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
    const n = min.slice(2);
    return n === '1' ? 'Every minute' : `Every ${n} minutes`;
  }

  // Every N hours: 0 */N * * *
  if (min === '0' && hour.startsWith('*/') && dom === '*' && mon === '*' && dow === '*') {
    const n = hour.slice(2);
    return n === '1' ? 'Every hour' : `Every ${n} hours`;
  }

  // Daily at HH:MM: M H * * *
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && dom === '*' && mon === '*' && dow === '*') {
    return `Daily at ${formatMinuteHour(min, hour)}`;
  }

  // Specific days of week: M H * * D
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && dom === '*' && mon === '*' && dow !== '*') {
    return `At ${formatMinuteHour(min, hour)}, ${parseDayRange(dow)}`;
  }

  // Monthly on Nth: M H N * *
  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && /^\d+$/.test(dom) && mon === '*' && dow === '*') {
    const d = parseInt(dom, 10);
    const suffix = d === 1 ? 'st' : d === 2 ? 'nd' : d === 3 ? 'rd' : 'th';
    return `Monthly on the ${d}${suffix} at ${formatMinuteHour(min, hour)}`;
  }

  // Hourly: 0 * * * *
  if (min === '0' && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
    return 'Every hour';
  }

  // Specific minute every hour: N * * * *
  if (/^\d+$/.test(min) && hour === '*' && dom === '*' && mon === '*' && dow === '*') {
    return `Every hour at :${min.padStart(2, '0')}`;
  }

  return expression;
}
