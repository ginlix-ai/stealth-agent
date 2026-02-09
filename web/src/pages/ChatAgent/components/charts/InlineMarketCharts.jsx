import React, { useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Cell,
  ResponsiveContainer, LabelList,
} from 'recharts';

// ─── Constants ──────────────────────────────────────────────────────

const GREEN = '#10b981';
const RED = '#ef4444';
const TEXT_COLOR = '#8b8fa3';
const CARD_BG = 'rgba(255,255,255,0.03)';
const CARD_BORDER = 'rgba(255,255,255,0.06)';

export const INLINE_CHART_TOOLS = new Set([
  'get_stock_daily_prices',
  'get_company_overview',
  'get_market_indices',
  'get_sector_performance',
]);

// ─── Helpers ────────────────────────────────────────────────────────

function downsample(arr, maxPoints = 60) {
  if (!arr || arr.length <= maxPoints) return arr;
  const step = arr.length / maxPoints;
  const result = [];
  for (let i = 0; i < maxPoints; i++) {
    result.push(arr[Math.floor(i * step)]);
  }
  // Always include last point
  if (result[result.length - 1] !== arr[arr.length - 1]) {
    result.push(arr[arr.length - 1]);
  }
  return result;
}

function formatCompactNumber(num) {
  if (num == null) return 'N/A';
  if (Math.abs(num) >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
  if (Math.abs(num) >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
  if (Math.abs(num) >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return typeof num === 'number' ? num.toFixed(2) : String(num);
}

function formatPct(val) {
  if (val == null) return 'N/A';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}

const cardStyle = {
  background: CARD_BG,
  border: `1px solid ${CARD_BORDER}`,
  borderRadius: 8,
  padding: '12px 14px',
  cursor: 'pointer',
  transition: 'border-color 0.15s',
};

const ABBREVIATIONS = {
  'Consumer Cyclical': 'Cons. Cyclical',
  'Consumer Defensive': 'Cons. Defensive',
  'Communication Services': 'Comm. Services',
  'Financial Services': 'Financial Svcs',
  'Basic Materials': 'Basic Materials',
  'Real Estate': 'Real Estate',
};

function abbreviateSector(name) {
  return ABBREVIATIONS[name] || name;
}

// ─── InlineStockPriceCard ───────────────────────────────────────────

export function InlineStockPriceCard({ artifact, onClick }) {
  const { symbol, ohlcv, stats } = artifact || {};

  const sparkData = useMemo(() => {
    if (!ohlcv?.length) return [];
    return downsample(ohlcv).map((d) => ({ close: d.close }));
  }, [ohlcv]);

  if (!ohlcv?.length) return null;

  const lastClose = ohlcv[ohlcv.length - 1]?.close;
  const firstDate = ohlcv[0]?.date;
  const lastDate = ohlcv[ohlcv.length - 1]?.date;
  const changePct = stats?.period_change_pct;
  const isPositive = (changePct ?? 0) >= 0;
  const color = isPositive ? GREEN : RED;
  const gradientId = `sparkGrad-${symbol || 'stock'}`;

  // Period label from date range
  const periodLabel = firstDate && lastDate ? `${firstDate} — ${lastDate}` : '';

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      {/* Header row: symbol + price + change */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 2 }}>
        <span style={{ fontWeight: 700, color: '#fff', fontSize: 15 }}>{symbol}</span>
        {lastClose != null && (
          <span style={{ color: '#fff', fontSize: 15, fontWeight: 600 }}>${lastClose.toFixed(2)}</span>
        )}
        {changePct != null && (
          <span style={{ color, fontSize: 13, fontWeight: 600 }}>
            {formatPct(changePct)}
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 11, color: TEXT_COLOR }}>
          {periodLabel}
        </span>
      </div>

      {/* Sparkline */}
      <div style={{ width: '100%', height: 64 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkData} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <YAxis type="number" domain={['dataMin', 'dataMax']} hide />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#${gradientId})`}
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Footer stats */}
      {stats && (
        <div
          style={{
            display: 'flex',
            gap: 12,
            marginTop: 4,
            fontSize: 11,
            color: TEXT_COLOR,
            flexWrap: 'wrap',
          }}
        >
          {stats.period_high != null && (
            <span>H: ${stats.period_high.toFixed(2)}</span>
          )}
          {stats.period_low != null && (
            <span>L: ${stats.period_low.toFixed(2)}</span>
          )}
          {stats.avg_volume != null && (
            <span>Vol: {formatCompactNumber(stats.avg_volume)}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── InlineCompanyOverviewCard ───────────────────────────────────────

function formatMarketCap(num) {
  if (num == null) return 'N/A';
  if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toLocaleString()}`;
}

export function InlineCompanyOverviewCard({ artifact, onClick }) {
  const { symbol, name, quote } = artifact || {};
  if (!quote) return null;

  const changeColor = (quote.change ?? 0) >= 0 ? GREEN : RED;

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      {/* Company name + symbol */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <span style={{ fontWeight: 700, color: '#fff', fontSize: 16 }}>
          {name || symbol}
        </span>
        {name && (
          <span style={{ fontSize: 13, color: TEXT_COLOR }}>{symbol}</span>
        )}
      </div>

      {/* Price + change */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
        {quote.price != null && (
          <span style={{ fontSize: 22, fontWeight: 700, color: '#fff' }}>
            ${quote.price.toFixed(2)}
          </span>
        )}
        {quote.change != null && (
          <span style={{ fontSize: 14, color: changeColor, fontWeight: 500 }}>
            {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)} ({quote.changePct?.toFixed(2)}%)
          </span>
        )}
      </div>

      {/* Key stats grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '2px 20px',
          fontSize: 12,
          color: TEXT_COLOR,
        }}
      >
        {quote.open != null && (
          <QuoteRow label="Open" value={`$${quote.open.toFixed(2)}`} />
        )}
        {quote.previousClose != null && (
          <QuoteRow label="Prev Close" value={`$${quote.previousClose.toFixed(2)}`} />
        )}
        {quote.dayLow != null && quote.dayHigh != null && (
          <QuoteRow label="Day Range" value={`$${quote.dayLow.toFixed(2)} - $${quote.dayHigh.toFixed(2)}`} />
        )}
        {quote.yearLow != null && quote.yearHigh != null && (
          <QuoteRow label="52W Range" value={`$${quote.yearLow.toFixed(2)} - $${quote.yearHigh.toFixed(2)}`} />
        )}
        {quote.volume != null && (
          <QuoteRow label="Volume" value={formatCompactNumber(quote.volume)} />
        )}
        {quote.marketCap != null && (
          <QuoteRow label="Market Cap" value={formatMarketCap(quote.marketCap)} />
        )}
      </div>
    </div>
  );
}

function QuoteRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
      <span style={{ opacity: 0.7 }}>{label}</span>
      <span style={{ color: '#fff', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ─── InlineMarketIndicesCard ────────────────────────────────────────

export function InlineMarketIndicesCard({ artifact, onClick }) {
  const indices = artifact?.indices;
  if (!indices || Object.keys(indices).length === 0) return null;

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      <div style={{ fontWeight: 600, color: '#fff', fontSize: 13, marginBottom: 8 }}>
        Market Indices
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {Object.entries(indices).map(([sym, data]) => {
          const lastClose = data.ohlcv?.[data.ohlcv.length - 1]?.close;
          const changePct = data.stats?.period_change_pct;
          const color = (changePct ?? 0) >= 0 ? GREEN : RED;
          return (
            <div
              key={sym}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '3px 0',
                fontSize: 12,
              }}
            >
              <span style={{ color: TEXT_COLOR }}>{data.name || sym}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {lastClose != null && (
                  <span style={{ color: '#fff', fontWeight: 500 }}>
                    {lastClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                )}
                {changePct != null && (
                  <span style={{ color, fontWeight: 500, minWidth: 55, textAlign: 'right' }}>
                    {formatPct(changePct)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── InlineSectorPerformanceCard ────────────────────────────────────

export function InlineSectorPerformanceCard({ artifact, onClick }) {
  const sectors = artifact?.sectors;
  if (!sectors?.length) return null;

  const chartData = sectors
    .slice()
    .sort((a, b) => (b.changesPercentage || 0) - (a.changesPercentage || 0))
    .map((s) => ({
      name: abbreviateSector(s.sector || 'N/A'),
      value: s.changesPercentage || 0,
      fill: (s.changesPercentage || 0) >= 0 ? GREEN : RED,
      label: formatPct(s.changesPercentage || 0),
    }));

  const barHeight = 22;
  const chartHeight = Math.min(chartData.length * barHeight + 20, 280);

  return (
    <div
      style={cardStyle}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
    >
      <div style={{ fontWeight: 600, color: '#fff', fontSize: 13, marginBottom: 6 }}>
        Sector Performance
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ left: 0, right: 50, top: 0, bottom: 0 }}
        >
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={100}
            tick={{ fill: TEXT_COLOR, fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14} isAnimationActive={false}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
            <LabelList
              dataKey="label"
              position="right"
              style={{ fill: TEXT_COLOR, fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
