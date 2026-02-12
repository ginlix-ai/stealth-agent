import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Tooltip } from 'antd';

const SIZE = 16;
const STROKE_WIDTH = 1.5;
const RADIUS = (SIZE - STROKE_WIDTH) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function getColor(pct) {
  if (pct > 0.85) return '#ef4444';
  if (pct > 0.60) return '#eab308';
  return '#22c55e';
}

function fmt(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function TokenUsageRing({ tokenUsage }) {
  const { totalInput, totalOutput, lastOutput, total, threshold } = tokenUsage;

  const pct = useMemo(() => Math.min(total / threshold, 1), [total, threshold]);

  const color = getColor(pct);
  const dashOffset = CIRCUMFERENCE * (1 - pct);

  const tooltipContent = (
    <div style={{ fontSize: 12, lineHeight: 1.7 }}>
      <div style={{ marginBottom: 2 }}><strong>Context window</strong></div>
      <div>Total input&ensp;<span style={{ opacity: 0.7 }}>{fmt(totalInput)}</span></div>
      <div>Total output&ensp;<span style={{ opacity: 0.7 }}>{fmt(totalOutput)}</span></div>
      <div>Last output&ensp;<span style={{ opacity: 0.7 }}>{fmt(lastOutput)}</span></div>
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.15)', marginTop: 4, paddingTop: 4 }}>
        Effective window&ensp;<span style={{ opacity: 0.7 }}>{fmt(total)} / {fmt(threshold)}</span>
        <span style={{ marginLeft: 6, color }}>{Math.round(pct * 100)}%</span>
      </div>
    </div>
  );

  return (
    <Tooltip title={tooltipContent} placement="top" trigger="click">
      <div
        className="inline-flex items-center justify-center"
        style={{ width: SIZE, height: SIZE, cursor: 'pointer', marginLeft: 2 }}
      >
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={STROKE_WIDTH}
          />
          <motion.circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            initial={false}
            animate={{ strokeDashoffset: dashOffset }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
            style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
          />
        </svg>
      </div>
    </Tooltip>
  );
}
