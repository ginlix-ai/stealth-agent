import React, { useEffect, useRef, useState, useImperativeHandle, forwardRef, useCallback } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import html2canvas from 'html2canvas';
import './TradingChart.css';
import { fetchStockData } from '../utils/api';

// --- O(n) Indicator Calculations ---

/**
 * Sliding-window Simple Moving Average — O(n)
 */
function calculateMA(data, period) {
  if (data.length < period) return [];
  const result = [];
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i].close;
  }
  result.push({ time: data[period - 1].time, value: sum / period });
  for (let i = period; i < data.length; i++) {
    sum += data[i].close - data[i - period].close;
    const value = sum / period;
    if (!isNaN(value) && isFinite(value)) {
      result.push({ time: data[i].time, value });
    }
  }
  return result;
}

/**
 * Wilder's smoothed RSI — O(n), correct algorithm
 */
function calculateRSI(data, period = 14) {
  if (data.length < period + 1) return [];
  const result = [];

  // Calculate price changes
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const change = data[i].close - data[i - 1].close;
    if (change > 0) avgGain += change;
    else avgLoss += -change;
  }
  avgGain /= period;
  avgLoss /= period;

  // First RSI value
  const firstRS = avgLoss === 0 ? 100 : avgGain / avgLoss;
  const firstRSI = avgLoss === 0 ? 100 : 100 - 100 / (1 + firstRS);
  result.push({ time: data[period].time, value: firstRSI });

  // Wilder's exponential smoothing for subsequent values
  for (let i = period + 1; i < data.length; i++) {
    const change = data[i].close - data[i - 1].close;
    const currentGain = change > 0 ? change : 0;
    const currentLoss = change < 0 ? -change : 0;
    avgGain = (avgGain * (period - 1) + currentGain) / period;
    avgLoss = (avgLoss * (period - 1) + currentLoss) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);
    if (!isNaN(rsi) && isFinite(rsi)) {
      result.push({ time: data[i].time, value: rsi });
    }
  }
  return result;
}

// --- Chart theme constants ---
const CHART_BG = '#0f1422';
const CHART_TEXT = '#8b8fa3';
const CHART_GRID = '#1a1f35';

const INTERVALS = [
  { key: '1min',  label: '1m'  },
  { key: '5min',  label: '5m'  },
  { key: '15min', label: '15m' },
  { key: '30min', label: '30m' },
  { key: '1hour', label: '1H'  },
  { key: '4hour', label: '4H'  },
  { key: '1day',  label: '1D'  },
];

// Days of history per interval for initial load
const INITIAL_LOAD_DAYS = {
  '1min': 7, '5min': 30, '15min': 60, '30min': 120,
  '1hour': 180, '4hour': 365, '1day': 0,  // 0 = full history
};

// Days to prepend on scroll-left per interval
const SCROLL_CHUNK_DAYS = {
  '1min': 5, '5min': 20, '15min': 30, '30min': 60,
  '1hour': 120, '4hour': 180, '1day': 365,
};

// Scroll-load: how close to left edge (in bars) before fetching more data
const SCROLL_LOAD_THRESHOLD = 20;
// Debounce delay for visible range changes (ms)
const RANGE_CHANGE_DEBOUNCE_MS = 300;
// Resize debounce delay (ms)
const RESIZE_DEBOUNCE_MS = 150;

// --- MA / RSI / Volume configuration ---
const MA_CONFIGS = [
  { period: 5,   color: '#22d3ee', label: 'MA5'   },  // cyan
  { period: 10,  color: '#34d399', label: 'MA10'  },  // green
  { period: 20,  color: '#fbbf24', label: 'MA20'  },  // yellow
  { period: 50,  color: '#3b82f6', label: 'MA50'  },  // blue
  { period: 100, color: '#a78bfa', label: 'MA100' },  // purple
  { period: 200, color: '#f59e0b', label: 'MA200' },  // orange
];
const DEFAULT_ENABLED_MA = [20, 50];
const RSI_PERIODS = [7, 14, 21];

// Approximate trading bars per day per interval (6.5h session)
const BARS_PER_DAY = {
  '1min': 390, '5min': 78, '15min': 26, '30min': 13,
  '1hour': 7, '4hour': 2, '1day': 1,
};

const TradingChart = React.memo(forwardRef(({ symbol, interval = '1day', onIntervalChange, onCapture, onStockMeta }, ref) => {
  const chartContainerRef = useRef();
  const rsiChartContainerRef = useRef();
  const chartRef = useRef();
  const rsiChartRef = useRef();
  const candlestickSeriesRef = useRef();
  const rsiSeriesRef = useRef();
  const volumeSeriesRef = useRef(null);
  const maSeriesRefs = useRef({});

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdateTime, setLastUpdateTime] = useState(null);
  const [rsiValue, setRsiValue] = useState(null);
  const [isMockData, setIsMockData] = useState(false);

  // MA / RSI config state
  const [enabledMaPeriods, setEnabledMaPeriods] = useState(DEFAULT_ENABLED_MA);
  const [rsiPeriod, setRsiPeriod] = useState(14);
  const [maValues, setMaValues] = useState({});

  // Refs for stable callbacks (avoid stale closures)
  const enabledMaPeriodsRef = useRef(DEFAULT_ENABLED_MA);
  const rsiPeriodRef = useRef(14);

  // Keep refs synced with state
  useEffect(() => { enabledMaPeriodsRef.current = enabledMaPeriods; }, [enabledMaPeriods]);
  useEffect(() => { rsiPeriodRef.current = rsiPeriod; }, [rsiPeriod]);

  // Refs for scroll-based loading
  const allDataRef = useRef([]);
  const oldestDateRef = useRef(null);
  const fetchingRef = useRef(false);
  const rangeChangeTimerRef = useRef(null);
  const rangeUnsubRef = useRef(null);

  useImperativeHandle(ref, () => ({
    captureChart: async () => {
      if (!chartContainerRef.current) return null;
      try {
        const canvas = await html2canvas(chartContainerRef.current, {
          backgroundColor: CHART_BG,
          scale: 2,
          logging: false,
        });
        return new Promise((resolve) => {
          canvas.toBlob((blob) => resolve(blob), 'image/png');
        });
      } catch (err) {
        console.error('Chart capture failed:', err);
        return null;
      }
    },
    captureChartAsDataUrl: async () => {
      const container = chartContainerRef.current?.parentElement; // .charts-container
      if (!container) return null;
      try {
        const canvas = await html2canvas(container, {
          backgroundColor: CHART_BG,
          scale: 1,
          logging: false,
        });
        return canvas.toDataURL('image/jpeg', 0.85);
      } catch (err) {
        console.error('Chart capture failed:', err);
        return null;
      }
    },
    getChartMetadata: () => {
      const data = allDataRef.current;
      if (!data || data.length === 0) return null;

      const firstTime = data[0].time;
      const lastTime = data[data.length - 1].time;
      const formatDate = (ts) => new Date(ts * 1000).toISOString().split('T')[0];

      // Current indicator values
      const enabledMAs = enabledMaPeriodsRef.current;
      const maInfo = enabledMAs
        .filter((p) => maValues[p] != null)
        .map((p) => `MA${p}: ${maValues[p]}`);

      const lastCandle = data[data.length - 1];

      return {
        dateRange: { from: formatDate(firstTime), to: formatDate(lastTime) },
        dataPoints: data.length,
        enabledMAs,
        maValues: Object.fromEntries(
          enabledMAs.filter((p) => maValues[p] != null).map((p) => [p, maValues[p]])
        ),
        maDescription: maInfo.length > 0 ? maInfo.join(', ') : null,
        rsiPeriod: rsiPeriodRef.current,
        rsiValue: rsiValue,
        lastCandle: {
          open: lastCandle.open,
          high: lastCandle.high,
          low: lastCandle.low,
          close: lastCandle.close,
          volume: lastCandle.volume,
        },
      };
    },
  }));

  // --- Update series data helper (used by both initial load and scroll load) ---
  const updateSeriesData = useCallback((data) => {
    // Candlestick
    if (candlestickSeriesRef.current) {
      candlestickSeriesRef.current.setData(data);
    }

    // Volume histogram
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.setData(data.map((d, i) => ({
        time: d.time,
        value: d.volume || 0,
        color: i > 0 && d.close >= data[i - 1].close
          ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
      })));
    }

    // All MAs — compute all enabled, clear disabled
    const enabled = enabledMaPeriodsRef.current;
    const newMaValues = {};
    MA_CONFIGS.forEach(({ period }) => {
      const series = maSeriesRefs.current[period];
      if (!series) return;
      if (enabled.includes(period)) {
        const maData = calculateMA(data, period);
        series.setData(maData);
        const last = maData[maData.length - 1]?.value;
        if (last != null) newMaValues[period] = last.toFixed(2);
      } else {
        series.setData([]);
      }
    });
    setMaValues(newMaValues);

    // RSI
    const currentRsiPeriod = rsiPeriodRef.current;
    const rsiData = calculateRSI(data, currentRsiPeriod);
    if (rsiData.length > 0 && rsiSeriesRef.current) {
      rsiSeriesRef.current.setData(rsiData);
      const lastRsi = rsiData[rsiData.length - 1]?.value;
      if (lastRsi != null) setRsiValue(lastRsi.toFixed(0));
      if (rsiChartRef.current) rsiChartRef.current.timeScale().fitContent();
    }
  }, []);

  // --- Scroll-based lazy loading ---
  const handleScrollLoadMore = useCallback(async () => {
    if (fetchingRef.current || !oldestDateRef.current) return;
    fetchingRef.current = true;

    try {
      const oldest = new Date(oldestDateRef.current * 1000);
      const toDate = new Date(oldest);
      toDate.setDate(toDate.getDate() - 1); // Day before current oldest
      const fromDate = new Date(toDate);
      fromDate.setDate(fromDate.getDate() - SCROLL_CHUNK_DAYS[interval]);

      const fromStr = fromDate.toISOString().split('T')[0];
      const toStr = toDate.toISOString().split('T')[0];

      const result = await fetchStockData(symbol, interval, fromStr, toStr);
      const newData = result?.data;

      if (newData && Array.isArray(newData) && newData.length > 0) {
        // Merge: deduplicate by timestamp, sort
        const existingMap = new Map(allDataRef.current.map((d) => [d.time, d]));
        newData.forEach((d) => {
          if (!existingMap.has(d.time)) existingMap.set(d.time, d);
        });
        const merged = Array.from(existingMap.values()).sort((a, b) => a.time - b.time);
        allDataRef.current = merged;
        oldestDateRef.current = merged[0].time;
        updateSeriesData(merged);
      }
    } catch (err) {
      console.warn('Scroll-load fetch failed:', err);
    } finally {
      fetchingRef.current = false;
    }
  }, [symbol, interval, updateSeriesData]);

  // --- Backfill older data when a newly-enabled MA needs more bars ---
  const backfillForMaPeriod = useCallback(async (period) => {
    const currentLen = allDataRef.current.length;
    if (currentLen >= period || fetchingRef.current || !oldestDateRef.current) return;

    fetchingRef.current = true;
    try {
      const deficit = period - currentLen;
      // Convert bar deficit to calendar days (1.5x for weekends/holidays)
      const extraDays = Math.ceil((deficit / (BARS_PER_DAY[interval] || 1)) * 1.5);

      const oldest = new Date(oldestDateRef.current * 1000);
      const toDate = new Date(oldest);
      toDate.setDate(toDate.getDate() - 1);
      const fromDate = new Date(toDate);
      fromDate.setDate(fromDate.getDate() - extraDays);

      const fromStr = fromDate.toISOString().split('T')[0];
      const toStr = toDate.toISOString().split('T')[0];

      const result = await fetchStockData(symbol, interval, fromStr, toStr);
      const newData = result?.data;

      if (newData && Array.isArray(newData) && newData.length > 0) {
        const existingMap = new Map(allDataRef.current.map((d) => [d.time, d]));
        newData.forEach((d) => {
          if (!existingMap.has(d.time)) existingMap.set(d.time, d);
        });
        const merged = Array.from(existingMap.values()).sort((a, b) => a.time - b.time);
        allDataRef.current = merged;
        oldestDateRef.current = merged[0].time;
        updateSeriesData(merged);
      }
    } catch (err) {
      console.warn('MA backfill fetch failed:', err);
    } finally {
      fetchingRef.current = false;
    }
  }, [symbol, interval, updateSeriesData]);

  // --- Toggle handlers ---
  const handleToggleMa = useCallback((period) => {
    const isCurrentlyEnabled = enabledMaPeriodsRef.current.includes(period);
    // If enabling and current data is insufficient, backfill older data
    if (!isCurrentlyEnabled && allDataRef.current.length < period) {
      backfillForMaPeriod(period);
    }
    setEnabledMaPeriods(prev =>
      prev.includes(period) ? prev.filter(p => p !== period) : [...prev, period]
    );
  }, [backfillForMaPeriod]);

  const handleChangeRsiPeriod = useCallback((period) => {
    setRsiPeriod(period);
  }, []);

  // --- Effect 1: Chart creation (mount only) ---
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_BG },
        textColor: CHART_TEXT,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      grid: {
        vertLines: { color: CHART_GRID },
        horzLines: { color: CHART_GRID },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: CHART_GRID,
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: CHART_GRID,
        timeVisible: true,
        secondsVisible: false,
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: false,
        },
      },
    });
    chartRef.current = chart;

    candlestickSeriesRef.current = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // Volume histogram series
    volumeSeriesRef.current = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // All MA line series
    MA_CONFIGS.forEach(({ period, color }) => {
      maSeriesRefs.current[period] = chart.addLineSeries({
        color,
        lineWidth: 1.5,
        title: '',
        lastValueVisible: false,
        priceLineVisible: false,
      });
    });

    // RSI chart (deferred so DOM is ready)
    const rsiTimeout = setTimeout(() => {
      if (!rsiChartContainerRef.current || rsiChartRef.current) return;
      const rsiChart = createChart(rsiChartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: CHART_BG },
          textColor: CHART_TEXT,
        },
        width: rsiChartContainerRef.current.clientWidth,
        height: rsiChartContainerRef.current.clientHeight,
        grid: {
          vertLines: { color: CHART_GRID },
          horzLines: { color: CHART_GRID },
        },
        rightPriceScale: {
          borderColor: CHART_GRID,
          visible: true,
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
          borderColor: CHART_GRID,
          timeVisible: true,
          secondsVisible: false,
        },
      });
      rsiChartRef.current = rsiChart;
      rsiSeriesRef.current = rsiChart.addLineSeries({
        color: '#667eea',
        lineWidth: 2,
        priceFormat: { type: 'price', precision: 0, minMove: 1 },
      });
    }, 100);

    // Debounced resize handler
    let resizeTimer = null;
    const handleResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (chartContainerRef.current && chartRef.current) {
          chartRef.current.applyOptions({
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
        if (rsiChartContainerRef.current && rsiChartRef.current) {
          rsiChartRef.current.applyOptions({
            width: rsiChartContainerRef.current.clientWidth,
            height: rsiChartContainerRef.current.clientHeight,
          });
        }
      }, RESIZE_DEBOUNCE_MS);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(rsiTimeout);
      clearTimeout(resizeTimer);
      window.removeEventListener('resize', handleResize);

      // Unsubscribe scroll-load listener
      if (rangeUnsubRef.current) {
        rangeUnsubRef.current();
        rangeUnsubRef.current = null;
      }
      clearTimeout(rangeChangeTimerRef.current);

      candlestickSeriesRef.current = null;
      volumeSeriesRef.current = null;
      Object.keys(maSeriesRefs.current).forEach(k => { maSeriesRefs.current[k] = null; });
      rsiSeriesRef.current = null;

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      if (rsiChartRef.current) {
        rsiChartRef.current.remove();
        rsiChartRef.current = null;
      }
    };
  }, []); // Mount only

  // --- Effect 2: Data loading (on symbol or interval change) ---
  useEffect(() => {
    const abortController = new AbortController();

    // Reset scroll-load state
    allDataRef.current = [];
    oldestDateRef.current = null;
    fetchingRef.current = false;

    // Unsubscribe previous scroll listener
    if (rangeUnsubRef.current) {
      rangeUnsubRef.current();
      rangeUnsubRef.current = null;
    }

    const loadData = async () => {
      setLoading(true);
      setError(null);
      setIsMockData(false);

      try {
        // Compute date range based on interval, with overhead for the largest enabled MA
        const loadDays = INITIAL_LOAD_DAYS[interval];
        let fromDate, toDate;
        if (loadDays > 0) {
          const maxMaPeriod = Math.max(...enabledMaPeriodsRef.current, 0);
          const overheadDays = Math.ceil((maxMaPeriod / (BARS_PER_DAY[interval] || 1)) * 1.5); // 1.5x for weekends/holidays
          const now = new Date();
          toDate = now.toISOString().split('T')[0];
          const from = new Date(now);
          from.setDate(from.getDate() - loadDays - overheadDays);
          fromDate = from.toISOString().split('T')[0];
        }

        const result = await fetchStockData(symbol, interval, fromDate, toDate, { signal: abortController.signal });

        if (abortController.signal.aborted) return;

        const data = result?.data || [];
        const isReal = result?.isReal !== false;

        setIsMockData(!isReal);
        if (!isReal) {
          console.warn('[Mock Data] Displaying mock data. Reason:', result?.error || 'FMP API call failed');
        }

        if (Array.isArray(data) && data.length > 0) {
          allDataRef.current = data;
          oldestDateRef.current = data[0].time;

          updateSeriesData(data);

          if (chartRef.current) {
            chartRef.current.timeScale().fitContent();
          }
          setLastUpdateTime(new Date());
          setError(null);

          if (typeof onStockMeta === 'function' && result?.fiftyTwoWeekHigh != null && result?.fiftyTwoWeekLow != null) {
            onStockMeta({ fiftyTwoWeekHigh: result.fiftyTwoWeekHigh, fiftyTwoWeekLow: result.fiftyTwoWeekLow });
          }

          // Subscribe to visible range changes for scroll-based loading (debounced)
          if (chartRef.current) {
            const unsubscribe = chartRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
              clearTimeout(rangeChangeTimerRef.current);
              rangeChangeTimerRef.current = setTimeout(() => {
                if (range && range.from <= SCROLL_LOAD_THRESHOLD) {
                  handleScrollLoadMore();
                }
              }, RANGE_CHANGE_DEBOUNCE_MS);
            });
            rangeUnsubRef.current = unsubscribe;
          }
        } else {
          setError('Stock data not found');
          if (typeof onStockMeta === 'function') onStockMeta(null);
        }
      } catch (err) {
        if (abortController.signal.aborted) return;
        console.error('Failed to load stock data:', err);
        setError('Failed to load data. Please check FMP API configuration.');
        setIsMockData(true);
      } finally {
        if (!abortController.signal.aborted) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      abortController.abort();
    };
  }, [symbol, interval, onStockMeta, updateSeriesData, handleScrollLoadMore]);

  // --- Effect 3: TimeScale options per interval ---
  useEffect(() => {
    const isIntraday = interval !== '1day';
    const showSeconds = interval === '1min';
    const opts = { timeVisible: isIntraday, secondsVisible: showSeconds };
    if (chartRef.current) chartRef.current.applyOptions({ timeScale: opts });
    if (rsiChartRef.current) rsiChartRef.current.applyOptions({ timeScale: opts });
  }, [interval]);

  // --- Effect 4: Re-run updateSeriesData when MA/RSI config changes ---
  useEffect(() => {
    if (allDataRef.current.length > 0) {
      updateSeriesData(allDataRef.current);
    }
  }, [enabledMaPeriods, rsiPeriod, updateSeriesData]);

  return (
    <div className="trading-chart-container">
      {isMockData && (
        <div className="trading-chart-mock-warning">
          Currently displaying mock data (FMP API call failed). Please check if <code>VITE_FMP_API_KEY</code> in <code>.env</code> is set with a valid key and restart <code>npm run dev</code>.
        </div>
      )}
      <div className="chart-header">
        <div className="chart-info">
          <span className="chart-label">{interval === '1day' ? 'Daily' : INTERVALS.find(i => i.key === interval)?.label} Summary & Indicators</span>
          {lastUpdateTime && (
            <span className="update-time">
              Last update: {lastUpdateTime.toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="chart-indicators">
          {MA_CONFIGS.filter(({ period }) => enabledMaPeriods.includes(period)).map(({ period, color, label }) => (
            <span className="indicator-item" key={period}>
              <span className="indicator-color" style={{ backgroundColor: color }} />
              {label}: {maValues[period] ?? '\u2014'}
            </span>
          ))}
          <span className="indicator-item">
            <span className="indicator-color" style={{ backgroundColor: '#667eea' }} />
            RSI ({rsiPeriod}): {rsiValue ?? '\u2014'}
          </span>
        </div>
      </div>
      <div className="chart-tools">
        <div className="chart-tools-left">
          <div className="interval-selector">
            {INTERVALS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                className={`interval-btn${interval === key ? ' interval-btn-active' : ''}`}
                onClick={() => onIntervalChange?.(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="indicator-toggles">
            <span className="indicator-toggles-label">MA</span>
            {MA_CONFIGS.map(({ period, color, label }) => (
              <button
                key={period}
                type="button"
                className={`indicator-toggle-btn${enabledMaPeriods.includes(period) ? ' indicator-toggle-active' : ''}`}
                style={enabledMaPeriods.includes(period) ? { color, borderColor: color } : undefined}
                onClick={() => handleToggleMa(period)}
              >
                {period}
              </button>
            ))}
          </div>
          <div className="indicator-toggles">
            <span className="indicator-toggles-label">RSI</span>
            {RSI_PERIODS.map((p) => (
              <button
                key={p}
                type="button"
                className={`indicator-toggle-btn${rsiPeriod === p ? ' indicator-toggle-active' : ''}`}
                style={rsiPeriod === p ? { color: '#667eea', borderColor: '#667eea' } : undefined}
                onClick={() => handleChangeRsiPeriod(p)}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className="chart-tool-buttons">
          <button type="button" className="chart-tool-btn">+</button>
          <button type="button" className="chart-tool-btn">&minus;</button>
          <button type="button" className="chart-tool-btn">&#9998;</button>
          <button type="button" className="chart-tool-btn">T</button>
        </div>
      </div>
      <div
        className="charts-container chart-wheel-capture"
        onWheel={(e) => e.stopPropagation()}
        role="region"
        aria-label="K-line chart"
      >
        <div
          ref={chartContainerRef}
          className="chart-wrapper"
        />
        <div className="rsi-container">
          <div className="rsi-label">RSI ({rsiPeriod}): {rsiValue ?? '\u2014'}</div>
          <div className="rsi-chart-wrapper" ref={rsiChartContainerRef}></div>
        </div>
      </div>
      {loading && (
        <div className="chart-loading">
          <div>Loading...</div>
          <div className="chart-loading-hint">
            If there is no response for a long time, it may be due to API rate limiting. Please wait 1 second and refresh.
          </div>
        </div>
      )}
      {error && (
        <div className="chart-error">
          <div className="chart-error-title">Data Loading Failed</div>
          <div>{error}</div>
        </div>
      )}
    </div>
  );
}));

TradingChart.displayName = 'TradingChart';

export default TradingChart;
