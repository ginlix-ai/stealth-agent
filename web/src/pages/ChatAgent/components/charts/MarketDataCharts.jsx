import React, { useEffect, useRef, useMemo, useCallback, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { useNavigate, useParams } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LabelList,
  LineChart, Line, ReferenceLine,
} from 'recharts';
import { fetchStockData } from '../../../TradingCenter/utils/api';

// ─── Shared Constants ───────────────────────────────────────────────

const CHART_BG = '#0f1422';
const GRID_COLOR = '#1a1f35';
const TEXT_COLOR = '#8b8fa3';
const GREEN = '#10b981';
const RED = '#ef4444';
const MA_BLUE = '#3b82f6';
const MA_ORANGE = '#f59e0b';

const PIE_COLORS = ['#6155F5', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6'];
const ANALYST_COLORS = {
  'Strong Buy': '#10b981',
  'Buy': '#34d399',
  'Hold': '#f59e0b',
  'Sell': '#f87171',
  'Strong Sell': '#ef4444',
};

const formatNumber = (num) => {
  if (num == null) return 'N/A';
  if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(1)}K`;
  return typeof num === 'number' ? `$${num.toFixed(2)}` : String(num);
};

const formatPct = (val) => {
  if (val == null) return 'N/A';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
};

/**
 * Convert date string to lightweight-charts time value.
 * Daily dates ("2024-01-15") → kept as string (business day format).
 * Intraday datetimes ("2024-01-15 09:30:00") → UNIX timestamp (seconds).
 */
const toChartTime = (dateStr) => {
  if (!dateStr) return dateStr;
  // If it contains a space or T, it's a datetime → convert to UNIX timestamp
  if (dateStr.includes(' ') || dateStr.includes('T')) {
    return Math.floor(new Date(dateStr).getTime() / 1000);
  }
  return dateStr; // daily date string, lightweight-charts handles it natively
};

// ─── Scroll-load config (mirrors TradingCenter/TradingChart.jsx) ────

const SCROLL_LOAD_THRESHOLD = 20;
const RANGE_CHANGE_DEBOUNCE_MS = 300;
const SCROLL_CHUNK_DAYS = {
  '1min': 5, '5min': 20, '15min': 30, '30min': 60,
  '1hour': 120, '4hour': 180, '1day': 365, daily: 365,
};

/** Map chart_interval values to API interval params */
const INTERVAL_TO_API = {
  '5min': '5min', '15min': '15min', '30min': '30min',
  '1hour': '1hour', '4hour': '4hour', daily: '1day',
};

// ─── Open in Trading Center link ────────────────────────────────────

function OpenInTradingLink({ symbol }) {
  const navigate = useNavigate();
  const params = useParams();
  if (!symbol) return null;

  const handleClick = (e) => {
    e.stopPropagation();
    const qs = new URLSearchParams({ symbol });
    // Encode current chat route so TradingCenter can offer a "Return to Chat" button
    if (params.workspaceId && params.threadId) {
      qs.set('returnTo', `/chat/${params.workspaceId}/${params.threadId}`);
    }
    navigate(`/trading?${qs.toString()}`);
  };

  return (
    <button
      onClick={handleClick}
      style={{
        marginLeft: 'auto',
        fontSize: 11,
        color: '#6155F5',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '2px 0',
        whiteSpace: 'nowrap',
        opacity: 0.85,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.85')}
    >
      Open in Trading ↗
    </button>
  );
}

// Custom tooltip for dark theme
const DarkTooltip = ({ active, payload, label, formatter }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#1a1f35', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '8px 12px' }}>
      <p style={{ color: TEXT_COLOR, fontSize: 12, margin: 0 }}>{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color || '#fff', fontSize: 12, margin: '2px 0 0' }}>
          {formatter ? formatter(entry.value) : entry.value}
        </p>
      ))}
    </div>
  );
};

// ─── StockPriceChart ────────────────────────────────────────────────

export function StockPriceChart({ data }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const maSeriesRefs = useRef({});

  // Prefer chart_ohlcv (intraday) when available, fall back to daily ohlcv
  const initialOhlcv = data?.chart_ohlcv?.length > 0 ? data.chart_ohlcv : data?.ohlcv;
  const chartInterval = data?.chart_interval || 'daily';
  const symbol = data?.symbol;

  // Scroll-load state (refs for stable closures)
  const allDataRef = useRef([]);
  const oldestTimeRef = useRef(null);
  const fetchingRef = useRef(false);
  const rangeTimerRef = useRef(null);
  const rangeUnsubRef = useRef(null);

  // Helper: set data on all series
  const updateAllSeries = useCallback((chartData) => {
    if (candleSeriesRef.current) {
      candleSeriesRef.current.setData(chartData.map((d) => ({
        time: d.time, open: d.open, high: d.high, low: d.low, close: d.close,
      })));
    }
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.setData(chartData.map((d, i) => ({
        time: d.time,
        value: d.volume || 0,
        color: i > 0 && d.close >= chartData[i - 1].close
          ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
      })));
    }
    // Update MAs
    [{ period: 20, color: MA_BLUE }, { period: 50, color: MA_ORANGE }].forEach(({ period }) => {
      const series = maSeriesRefs.current[period];
      if (!series) return;
      if (chartData.length < period) { series.setData([]); return; }
      const maData = [];
      let sum = 0;
      for (let i = 0; i < period; i++) sum += chartData[i].close;
      maData.push({ time: chartData[period - 1].time, value: sum / period });
      for (let i = period; i < chartData.length; i++) {
        sum += chartData[i].close - chartData[i - period].close;
        maData.push({ time: chartData[i].time, value: sum / period });
      }
      series.setData(maData);
    });
  }, []);

  // Scroll-load handler
  const handleScrollLoadMore = useCallback(async () => {
    if (fetchingRef.current || !oldestTimeRef.current || !symbol) return;
    const apiInterval = INTERVAL_TO_API[chartInterval];
    if (!apiInterval) return;

    fetchingRef.current = true;
    try {
      const oldest = new Date(oldestTimeRef.current * 1000);
      const toDate = new Date(oldest);
      toDate.setDate(toDate.getDate() - 1);
      const fromDate = new Date(toDate);
      fromDate.setDate(fromDate.getDate() - (SCROLL_CHUNK_DAYS[chartInterval] || 90));

      const result = await fetchStockData(
        symbol, apiInterval,
        fromDate.toISOString().split('T')[0],
        toDate.toISOString().split('T')[0],
      );
      const newData = result?.data;

      if (newData && Array.isArray(newData) && newData.length > 0) {
        const existingMap = new Map(allDataRef.current.map((d) => [d.time, d]));
        newData.forEach((d) => { if (!existingMap.has(d.time)) existingMap.set(d.time, d); });
        const merged = Array.from(existingMap.values()).sort((a, b) => a.time - b.time);
        allDataRef.current = merged;
        oldestTimeRef.current = merged[0].time;
        updateAllSeries(merged);
      }
    } catch (err) {
      console.warn('Detail chart scroll-load failed:', err);
    } finally {
      fetchingRef.current = false;
    }
  }, [symbol, chartInterval, updateAllSeries]);

  useEffect(() => {
    if (!containerRef.current || !initialOhlcv?.length) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    if (rangeUnsubRef.current) { rangeUnsubRef.current(); rangeUnsubRef.current = null; }
    candleSeriesRef.current = null;
    volumeSeriesRef.current = null;
    maSeriesRefs.current = {};

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_BG },
        textColor: TEXT_COLOR,
      },
      width: containerRef.current.clientWidth,
      height: 360,
      grid: {
        vertLines: { color: GRID_COLOR },
        horzLines: { color: GRID_COLOR },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: GRID_COLOR },
      timeScale: {
        borderColor: GRID_COLOR,
        timeVisible: chartInterval !== 'daily',
        handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true },
      },
    });
    chartRef.current = chart;

    // Candlestick series
    candleSeriesRef.current = chart.addCandlestickSeries({
      upColor: GREEN, downColor: RED,
      borderDownColor: RED, borderUpColor: GREEN,
      wickDownColor: RED, wickUpColor: GREEN,
    });

    // Volume histogram series (bottom 20%)
    volumeSeriesRef.current = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // MA line series (daily only)
    if (chartInterval === 'daily') {
      [{ period: 20, color: MA_BLUE }, { period: 50, color: MA_ORANGE }].forEach(({ period, color }) => {
        maSeriesRefs.current[period] = chart.addLineSeries({
          color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
        });
      });
    }

    // Convert initial OHLCV to lightweight-charts format
    const chartData = initialOhlcv.map((d) => ({
      time: toChartTime(d.date),
      open: d.open, high: d.high, low: d.low, close: d.close, volume: d.volume || 0,
    })).sort((a, b) => a.time - b.time);

    allDataRef.current = chartData;
    oldestTimeRef.current = chartData[0]?.time;
    updateAllSeries(chartData);

    chart.timeScale().fitContent();

    // Subscribe to visible range changes for scroll-based loading
    const unsubscribe = chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      clearTimeout(rangeTimerRef.current);
      rangeTimerRef.current = setTimeout(() => {
        if (range && range.from <= SCROLL_LOAD_THRESHOLD) {
          handleScrollLoadMore();
        }
      }, RANGE_CHANGE_DEBOUNCE_MS);
    });
    rangeUnsubRef.current = unsubscribe;

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      clearTimeout(rangeTimerRef.current);
      if (rangeUnsubRef.current) { rangeUnsubRef.current(); rangeUnsubRef.current = null; }
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
    };
  }, [initialOhlcv, chartInterval, updateAllSeries, handleScrollLoadMore]);

  if (!initialOhlcv?.length) {
    return <div style={{ color: TEXT_COLOR, padding: 16 }}>No price data available</div>;
  }

  const INTERVAL_LABELS = { '5min': '5m', '15min': '15m', '30min': '30m', '1hour': '1H', '4hour': '4H', daily: 'D' };

  return (
    <div>
      <div className="flex items-center gap-3 mb-2" style={{ fontSize: 13, color: TEXT_COLOR }}>
        <span style={{ fontWeight: 600, color: '#fff' }}>{data.symbol}</span>
        {chartInterval && (
          <span style={{
            fontSize: 11,
            padding: '1px 6px',
            borderRadius: 3,
            background: 'rgba(255,255,255,0.08)',
            color: TEXT_COLOR,
          }}>
            {INTERVAL_LABELS[chartInterval] || chartInterval}
          </span>
        )}
        {data.stats?.period_change_pct != null && (
          <span style={{ color: data.stats.period_change_pct >= 0 ? GREEN : RED }}>
            {formatPct(data.stats.period_change_pct)}
          </span>
        )}
        {chartInterval === 'daily' && (
          <>
            <span className="flex items-center gap-1">
              <span style={{ width: 12, height: 2, background: MA_BLUE, display: 'inline-block' }} /> MA20
            </span>
            <span className="flex items-center gap-1">
              <span style={{ width: 12, height: 2, background: MA_ORANGE, display: 'inline-block' }} /> MA50
            </span>
          </>
        )}
        <OpenInTradingLink symbol={data.symbol} />
      </div>
      <div ref={containerRef} style={{ width: '100%', height: 360 }} />
      <StockStatsCard stats={data.stats} />
    </div>
  );
}

// ─── StockStatsCard ─────────────────────────────────────────────────

function StockStatsCard({ stats }) {
  if (!stats) return null;

  const items = [
    { label: 'Period Change', value: stats.period_change_pct != null ? formatPct(stats.period_change_pct) : null, color: stats.period_change_pct >= 0 ? GREEN : RED },
    { label: 'Period High', value: stats.period_high != null ? `$${stats.period_high.toFixed(2)}` : null },
    { label: 'Period Low', value: stats.period_low != null ? `$${stats.period_low.toFixed(2)}` : null },
    { label: 'Avg Volume', value: stats.avg_volume != null ? formatNumber(stats.avg_volume).replace('$', '') : null },
    { label: 'Volatility', value: stats.volatility != null ? `${(stats.volatility * 100).toFixed(1)}%` : null },
    { label: 'MA 20', value: stats.ma_20 != null ? `$${stats.ma_20.toFixed(2)}` : null, labelColor: MA_BLUE },
    { label: 'MA 50', value: stats.ma_50 != null ? `$${stats.ma_50.toFixed(2)}` : null, labelColor: MA_ORANGE },
  ].filter((i) => i.value != null);

  if (items.length === 0) return null;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '8px 16px',
        marginTop: 12,
        padding: '10px 12px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 6,
        fontSize: 12,
      }}
    >
      {items.map((item) => (
        <div key={item.label}>
          <div style={{ color: item.labelColor || TEXT_COLOR, opacity: item.labelColor ? 1 : 0.7, marginBottom: 2 }}>
            {item.label}
          </div>
          <div style={{ color: item.color || '#fff', fontWeight: 500 }}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── SectorPerformanceChart ─────────────────────────────────────────

const SECTOR_ABBREVIATIONS = {
  'Consumer Cyclical': 'Cons. Cyclical',
  'Consumer Defensive': 'Cons. Defensive',
  'Communication Services': 'Comm. Services',
  'Financial Services': 'Financial Svcs',
};

export function SectorPerformanceChart({ data }) {
  const sectors = data?.sectors;
  if (!sectors?.length) {
    return <div style={{ color: TEXT_COLOR, padding: 16 }}>No sector data available</div>;
  }

  const chartData = sectors.map((s) => {
    const name = s.sector || 'N/A';
    return {
      name: SECTOR_ABBREVIATIONS[name] || name,
      value: s.changesPercentage || 0,
      fill: (s.changesPercentage || 0) >= 0 ? GREEN : RED,
      label: formatPct(s.changesPercentage || 0),
    };
  });

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
        Sector Performance
      </h4>
      <ResponsiveContainer width="100%" height={Math.max(chartData.length * 36, 200)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 50 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: TEXT_COLOR, fontSize: 11 }}
            axisLine={{ stroke: GRID_COLOR }}
            tickFormatter={(v) => `${v.toFixed(1)}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            tick={{ fill: TEXT_COLOR, fontSize: 11 }}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <Tooltip content={<DarkTooltip formatter={(v) => formatPct(v)} />} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
            <LabelList
              dataKey="label"
              position="right"
              style={{ fill: TEXT_COLOR, fontSize: 11 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── PerformanceBarChart ────────────────────────────────────────────

export function PerformanceBarChart({ performance }) {
  if (!performance || Object.keys(performance).length === 0) return null;

  const labels = { '1D': '1D', '5D': '5D', '1M': '1M', '3M': '3M', '6M': '6M', 'ytd': 'YTD', '1Y': '1Y', '3Y': '3Y', '5Y': '5Y' };
  const chartData = Object.entries(labels)
    .filter(([key]) => performance[key] != null)
    .map(([key, label]) => ({
      name: label,
      value: performance[key],
      fill: performance[key] >= 0 ? GREEN : RED,
    }));

  if (chartData.length === 0) return null;

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Price Performance
      </h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ left: -20, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: TEXT_COLOR, fontSize: 11 }}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <YAxis
            tick={{ fill: TEXT_COLOR, fontSize: 11 }}
            axisLine={{ stroke: GRID_COLOR }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip content={<DarkTooltip formatter={(v) => formatPct(v)} />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── AnalystRatingsChart ────────────────────────────────────────────

export function AnalystRatingsChart({ ratings }) {
  if (!ratings) return null;

  const chartData = [
    { name: 'Strong Buy', value: ratings.strongBuy || 0 },
    { name: 'Buy', value: ratings.buy || 0 },
    { name: 'Hold', value: ratings.hold || 0 },
    { name: 'Sell', value: ratings.sell || 0 },
    { name: 'Strong Sell', value: ratings.strongSell || 0 },
  ].filter((d) => d.value > 0);

  if (chartData.length === 0) return null;
  const total = chartData.reduce((s, d) => s + d.value, 0);

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Analyst Ratings
      </h4>
      <div style={{ position: 'relative' }}>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              dataKey="value"
              stroke="none"
            >
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={ANALYST_COLORS[entry.name] || '#666'} />
              ))}
            </Pie>
            <Legend
              wrapperStyle={{ fontSize: 11, color: TEXT_COLOR }}
              formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>}
            />
            <Tooltip content={<DarkTooltip formatter={(v) => `${v} (${((v / total) * 100).toFixed(0)}%)`} />} />
          </PieChart>
        </ResponsiveContainer>
        {/* Center consensus label */}
        <div
          style={{
            position: 'absolute',
            top: '38%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 700, color: '#fff', textTransform: 'uppercase' }}>
            {ratings.consensus || ''}
          </div>
          <div style={{ fontSize: 11, color: TEXT_COLOR }}>{total} ratings</div>
        </div>
      </div>
    </div>
  );
}

// ─── RevenueBreakdownChart ──────────────────────────────────────────

export function RevenueBreakdownChart({ revenueByProduct, revenueByGeo }) {
  const hasProduct = revenueByProduct && Object.keys(revenueByProduct).length > 0;
  const hasGeo = revenueByGeo && Object.keys(revenueByGeo).length > 0;

  if (!hasProduct && !hasGeo) return null;

  const buildPieData = (obj) => {
    return Object.entries(obj)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  };

  const renderPie = (data, title) => {
    const total = data.reduce((s, d) => s + d.value, 0);
    return (
      <div style={{ flex: 1, minWidth: 200 }}>
        <h5 style={{ color: TEXT_COLOR, fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
          {title}
        </h5>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={35}
              outerRadius={55}
              dataKey="value"
              stroke="none"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Legend
              wrapperStyle={{ fontSize: 10, color: TEXT_COLOR }}
              formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>}
            />
            <Tooltip
              content={<DarkTooltip formatter={(v) => `${formatNumber(v)} (${((v / total) * 100).toFixed(1)}%)`} />}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Revenue Breakdown
      </h4>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {hasProduct && renderPie(buildPieData(revenueByProduct), 'By Product')}
        {hasGeo && renderPie(buildPieData(revenueByGeo), 'By Geography')}
      </div>
    </div>
  );
}

// ─── QuarterlyRevenueChart ───────────────────────────────────────────

export function QuarterlyRevenueChart({ data }) {
  if (!data?.length) return null;

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Quarterly Revenue &amp; Net Income
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
          <XAxis dataKey="period" tick={{ fill: TEXT_COLOR, fontSize: 10 }} axisLine={{ stroke: GRID_COLOR }} />
          <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={{ stroke: GRID_COLOR }} tickFormatter={(v) => formatNumber(v).replace('$', '')} />
          <Tooltip content={<DarkTooltip formatter={(v) => formatNumber(v)} />} />
          <Legend wrapperStyle={{ fontSize: 11, color: TEXT_COLOR }} formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>} />
          <Bar dataKey="revenue" name="Revenue" fill="#6155F5" radius={[4, 4, 0, 0]} />
          <Bar dataKey="netIncome" name="Net Income" fill={GREEN} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── MarginsChart ───────────────────────────────────────────────────

export function MarginsChart({ data }) {
  if (!data?.length) return null;

  const chartData = data.map((d) => ({
    period: d.period,
    grossMargin: d.grossMargin != null ? d.grossMargin * 100 : null,
    operatingMargin: d.operatingMargin != null ? d.operatingMargin * 100 : null,
    netMargin: d.netMargin != null ? d.netMargin * 100 : null,
  }));

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Profit Margins
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ left: -10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
          <XAxis dataKey="period" tick={{ fill: TEXT_COLOR, fontSize: 10 }} axisLine={{ stroke: GRID_COLOR }} />
          <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={{ stroke: GRID_COLOR }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
          <Tooltip content={<DarkTooltip formatter={(v) => `${v?.toFixed(1)}%`} />} />
          <Legend wrapperStyle={{ fontSize: 11, color: TEXT_COLOR }} formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>} />
          <Line type="monotone" dataKey="grossMargin" name="Gross Margin" stroke="#6155F5" strokeWidth={2} dot={{ r: 3 }} connectNulls />
          <Line type="monotone" dataKey="operatingMargin" name="Operating Margin" stroke={MA_ORANGE} strokeWidth={2} dot={{ r: 3 }} connectNulls />
          <Line type="monotone" dataKey="netMargin" name="Net Margin" stroke={GREEN} strokeWidth={2} dot={{ r: 3 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── EarningsSurpriseChart ──────────────────────────────────────────

export function EarningsSurpriseChart({ data }) {
  if (!data?.length) return null;

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        EPS: Actual vs Estimate
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
          <XAxis dataKey="period" tick={{ fill: TEXT_COLOR, fontSize: 10 }} axisLine={{ stroke: GRID_COLOR }} />
          <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={{ stroke: GRID_COLOR }} tickFormatter={(v) => `$${v.toFixed(2)}`} />
          <Tooltip content={<DarkTooltip formatter={(v) => `$${v?.toFixed(2)}`} />} />
          <Legend wrapperStyle={{ fontSize: 11, color: TEXT_COLOR }} formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>} />
          <Bar dataKey="epsActual" name="EPS Actual" fill={GREEN} radius={[4, 4, 0, 0]} />
          <Bar dataKey="epsEstimate" name="EPS Estimate" fill="#4b5563" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── CashFlowChart ──────────────────────────────────────────────────

export function CashFlowChart({ data }) {
  if (!data?.length) return null;

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Cash Flow (Quarterly)
      </h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
          <XAxis dataKey="period" tick={{ fill: TEXT_COLOR, fontSize: 10 }} axisLine={{ stroke: GRID_COLOR }} />
          <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={{ stroke: GRID_COLOR }} tickFormatter={(v) => formatNumber(v).replace('$', '')} />
          <Tooltip content={<DarkTooltip formatter={(v) => formatNumber(v)} />} />
          <Legend wrapperStyle={{ fontSize: 11, color: TEXT_COLOR }} formatter={(val) => <span style={{ color: TEXT_COLOR }}>{val}</span>} />
          <ReferenceLine y={0} stroke={GRID_COLOR} />
          <Bar dataKey="operatingCashFlow" name="Operating CF" fill="#6155F5" radius={[4, 4, 0, 0]} />
          <Bar dataKey="capitalExpenditure" name="CapEx" fill={RED} radius={[4, 4, 0, 0]} />
          <Bar dataKey="freeCashFlow" name="Free CF" fill={GREEN} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── CompanyOverviewCard ────────────────────────────────────────────

export function CompanyOverviewCard({ data }) {
  const {
    symbol, name, quote, performance, analystRatings,
    revenueByProduct, revenueByGeo,
    quarterlyFundamentals, earningsSurprises, cashFlow,
  } = data || {};

  return (
    <div className="space-y-5">
      {/* Quote summary */}
      {quote && (
        <div>
          <div className="flex items-baseline gap-3 mb-3">
            <span style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>
              {name || symbol}
            </span>
            <span style={{ fontSize: 14, color: TEXT_COLOR }}>{symbol}</span>
            <OpenInTradingLink symbol={symbol} />
          </div>
          <div className="flex items-baseline gap-3 mb-3">
            <span style={{ fontSize: 24, fontWeight: 700, color: '#fff' }}>
              ${quote.price?.toFixed(2) || 'N/A'}
            </span>
            {quote.change != null && (
              <span style={{ fontSize: 14, color: quote.change >= 0 ? GREEN : RED }}>
                {quote.change >= 0 ? '+' : ''}{quote.change?.toFixed(2)} ({quote.changePct?.toFixed(2)}%)
              </span>
            )}
          </div>
          <div
            className="grid grid-cols-2 gap-x-6 gap-y-1"
            style={{ fontSize: 12, color: TEXT_COLOR }}
          >
            {quote.open != null && <QuoteStat label="Open" value={`$${quote.open.toFixed(2)}`} />}
            {quote.previousClose != null && <QuoteStat label="Prev Close" value={`$${quote.previousClose.toFixed(2)}`} />}
            {quote.dayLow != null && quote.dayHigh != null && (
              <QuoteStat label="Day Range" value={`$${quote.dayLow.toFixed(2)} - $${quote.dayHigh.toFixed(2)}`} />
            )}
            {quote.yearLow != null && quote.yearHigh != null && (
              <QuoteStat label="52W Range" value={`$${quote.yearLow.toFixed(2)} - $${quote.yearHigh.toFixed(2)}`} />
            )}
            {quote.volume != null && <QuoteStat label="Volume" value={formatNumber(quote.volume).replace('$', '')} />}
            {quote.marketCap != null && <QuoteStat label="Market Cap" value={formatNumber(quote.marketCap)} />}
          </div>
        </div>
      )}

      {/* Performance */}
      <PerformanceBarChart performance={performance} />

      {/* Analyst Ratings */}
      <AnalystRatingsChart ratings={analystRatings} />

      {/* Quarterly Revenue & Net Income */}
      <QuarterlyRevenueChart data={quarterlyFundamentals} />

      {/* Profit Margins */}
      <MarginsChart data={quarterlyFundamentals} />

      {/* EPS Actual vs Estimate */}
      <EarningsSurpriseChart data={earningsSurprises} />

      {/* Cash Flow */}
      <CashFlowChart data={cashFlow} />

      {/* Revenue Breakdown */}
      <RevenueBreakdownChart revenueByProduct={revenueByProduct} revenueByGeo={revenueByGeo} />
    </div>
  );
}

function QuoteStat({ label, value }) {
  return (
    <div className="flex justify-between py-0.5">
      <span style={{ opacity: 0.7 }}>{label}</span>
      <span style={{ color: '#fff' }}>{value}</span>
    </div>
  );
}

// ─── MarketIndicesChart ─────────────────────────────────────────────

export function MarketIndicesChart({ data }) {
  const indices = data?.indices;
  if (!indices || Object.keys(indices).length === 0) {
    return <div style={{ color: TEXT_COLOR, padding: 16 }}>No index data available</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {Object.entries(indices).map(([symbol, indexData]) => {
        const lastClose = indexData.ohlcv?.[indexData.ohlcv.length - 1]?.close;
        const changePct = indexData.stats?.period_change_pct;
        const changeColor = (changePct ?? 0) >= 0 ? GREEN : RED;
        const stats = indexData.stats;

        return (
          <div
            key={symbol}
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            {/* Header: name + price/change + trading link */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ color: '#fff', fontWeight: 600, fontSize: 13 }}>
                {indexData.name || symbol}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                {lastClose != null && (
                  <span style={{ color: '#fff', fontWeight: 500 }}>
                    {lastClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                )}
                {changePct != null && (
                  <span style={{ color: changeColor, fontWeight: 500 }}>
                    {formatPct(changePct)}
                  </span>
                )}
                <OpenInTradingLink symbol={symbol} />
              </div>
            </div>

            {/* Stats row */}
            {stats && (
              <div style={{ display: 'flex', gap: 12, fontSize: 11, color: TEXT_COLOR, marginBottom: 6 }}>
                {stats.ma_20 != null && <span>MA20: {stats.ma_20.toFixed(2)}</span>}
                {stats.ma_50 != null && <span>MA50: {stats.ma_50.toFixed(2)}</span>}
                {stats.volatility != null && <span>Vol: {(stats.volatility * 100).toFixed(1)}%</span>}
              </div>
            )}

            <MiniCandlestick
              ohlcv={indexData.chart_ohlcv?.length > 0 ? indexData.chart_ohlcv : indexData.ohlcv}
              height={160}
            />
          </div>
        );
      })}
    </div>
  );
}

// ─── StockScreenerTable ──────────────────────────────────────────────

export function StockScreenerTable({ data }) {
  const { results = [], filters = {}, count = 0 } = data || {};
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('desc');

  const handleSort = useCallback((key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }, [sortKey]);

  const sortedResults = useMemo(() => {
    if (!sortKey) return results;
    return [...results].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === 'string') return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    });
  }, [results, sortKey, sortDir]);

  if (!results.length) {
    return <div style={{ color: TEXT_COLOR, padding: 16 }}>No screener results available</div>;
  }

  const filterTags = Object.entries(filters).map(([k, v]) => `${k}: ${v}`);

  const columns = [
    { key: 'symbol', label: 'Symbol', width: 70 },
    { key: 'companyName', label: 'Company', width: 160 },
    { key: 'price', label: 'Price', width: 70, format: (v) => v != null ? `$${v.toFixed(2)}` : 'N/A' },
    { key: 'marketCap', label: 'Mkt Cap', width: 80, format: formatNumber },
    { key: 'sector', label: 'Sector', width: 110 },
    { key: 'industry', label: 'Industry', width: 120 },
    { key: 'beta', label: 'Beta', width: 55, format: (v) => v != null ? v.toFixed(2) : 'N/A' },
    { key: 'volume', label: 'Volume', width: 75, format: (v) => v != null ? formatNumber(v).replace('$', '') : 'N/A' },
    { key: 'lastAnnualDividend', label: 'Dividend', width: 65, format: (v) => v != null ? `$${v.toFixed(2)}` : 'N/A' },
    { key: 'exchangeShortName', label: 'Exchange', width: 70 },
    { key: 'country', label: 'Country', width: 55 },
    { key: 'changes', label: 'Change%', width: 70, format: (v) => v != null ? formatPct(v) : 'N/A', color: (v) => v != null ? (v >= 0 ? GREEN : RED) : TEXT_COLOR },
  ];

  const SortArrow = ({ col }) => {
    if (sortKey !== col) return null;
    return <span style={{ marginLeft: 2, fontSize: 10 }}>{sortDir === 'asc' ? '▲' : '▼'}</span>;
  };

  return (
    <div>
      <h4 style={{ color: '#fff', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
        Stock Screener — {count} result{count !== 1 ? 's' : ''}
      </h4>

      {/* Filter summary */}
      {filterTags.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {filterTags.map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 12,
                backgroundColor: 'rgba(97, 85, 245, 0.12)',
                color: 'rgba(255,255,255,0.7)',
                border: '1px solid rgba(97, 85, 245, 0.2)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Scrollable table */}
      <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: '70vh' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    position: 'sticky',
                    top: 0,
                    background: CHART_BG,
                    color: TEXT_COLOR,
                    fontWeight: 500,
                    padding: '6px 8px',
                    textAlign: 'left',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    minWidth: col.width,
                    userSelect: 'none',
                  }}
                >
                  {col.label}<SortArrow col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedResults.map((stock, i) => (
              <tr
                key={stock.symbol || i}
                style={{
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {columns.map((col) => {
                  const raw = stock[col.key];
                  const display = col.format ? col.format(raw) : (raw ?? 'N/A');
                  const cellColor = col.color ? col.color(raw) : (col.key === 'symbol' ? '#fff' : TEXT_COLOR);
                  return (
                    <td
                      key={col.key}
                      style={{
                        padding: '5px 8px',
                        color: cellColor,
                        fontWeight: col.key === 'symbol' ? 600 : 400,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: col.key === 'companyName' ? 160 : col.key === 'industry' ? 120 : undefined,
                      }}
                    >
                      {display}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MiniCandlestick({ ohlcv, height = 180 }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  // Detect if data is intraday (datetime strings with space or T)
  const isIntraday = ohlcv?.[0]?.date && (ohlcv[0].date.includes(' ') || ohlcv[0].date.includes('T'));

  useEffect(() => {
    if (!containerRef.current || !ohlcv?.length) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_BG },
        textColor: TEXT_COLOR,
      },
      width: containerRef.current.clientWidth,
      height,
      grid: {
        vertLines: { color: GRID_COLOR },
        horzLines: { color: GRID_COLOR },
      },
      rightPriceScale: { borderColor: GRID_COLOR },
      timeScale: { borderColor: GRID_COLOR, timeVisible: isIntraday },
    });
    chartRef.current = chart;

    const series = chart.addCandlestickSeries({
      upColor: GREEN,
      downColor: RED,
      borderDownColor: RED,
      borderUpColor: GREEN,
      wickDownColor: RED,
      wickUpColor: GREEN,
    });
    series.setData(
      ohlcv.map((d) => ({
        time: toChartTime(d.date),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }))
    );

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [ohlcv, height]);

  if (!ohlcv?.length) return null;
  return <div ref={containerRef} style={{ width: '100%', height }} />;
}
