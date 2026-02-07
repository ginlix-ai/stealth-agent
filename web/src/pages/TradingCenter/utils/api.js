/**
 * TradingCenter API utilities
 * All backend endpoints used by the TradingCenter page
 */
import { api, headers, DEFAULT_USER_ID } from '@/api/client';

/**
 * Search for stocks by keyword (symbol or company name).
 * Same API as Dashboard Add Watchlist: GET /api/v1/market-data/search/stocks
 * @param {string} query - Search keyword (e.g., "AAPL", "Apple", "Micro")
 * @param {number} limit - Maximum number of results (default: 50, max: 100)
 * @returns {Promise<{query: string, results: Array, count: number}>}
 */
export async function searchStocks(query, limit = 50) {
  if (!query || !query.trim()) {
    return { query: '', results: [], count: 0 };
  }
  try {
    const { data } = await api.get('/api/v1/market-data/search/stocks', {
      params: {
        query: query.trim(),
        limit: Math.min(Math.max(1, limit), 100),
      },
    });
    return data || { query: query.trim(), results: [], count: 0 };
  } catch (e) {
    console.error('Search stocks failed:', e?.response?.status, e?.response?.data, e?.message);
    return { query: query.trim(), results: [], count: 0 };
  }
}

/**
 * Fetch stock historical data for charting
 * Uses backend API endpoint: GET /api/v1/market-data/intraday/stocks/{symbol}
 *
 * @param {string} symbol - Stock symbol (e.g., 'AAPL', 'MSFT')
 * @param {string} interval - Data interval (default: '1hour' for daily-like view, supports: 1min, 5min, 15min, 30min, 1hour, 4hour)
 * @returns {Promise<{data: Array, isReal: boolean, error?: string}>} Chart data in lightweight-charts format
 */
export async function fetchStockData(symbol, interval = '1hour') {
  if (!symbol || !symbol.trim()) {
    return { data: [], isReal: false, error: 'Symbol is required' };
  }

  const symbolUpper = symbol.trim().toUpperCase();

  try {
    const { data } = await api.get(`/api/v1/market-data/intraday/stocks/${encodeURIComponent(symbolUpper)}`, {
      params: {
        interval: interval === '1day' ? '1hour' : interval,
      },
    });

    const dataPoints = data?.data || [];
    
    if (!Array.isArray(dataPoints) || dataPoints.length === 0) {
      return { data: [], isReal: false, error: 'No data available' };
    }

    // Convert backend format to lightweight-charts format
    // Backend returns: { date: "YYYY-MM-DD HH:MM:SS", open, high, low, close, volume }
    const chartData = dataPoints.map((point) => {
      const date = new Date(point.date);
      return {
        time: Math.floor(date.getTime() / 1000),
        open: parseFloat(point.open) || 0,
        high: parseFloat(point.high) || 0,
        low: parseFloat(point.low) || 0,
        close: parseFloat(point.close) || 0,
      };
    }).filter(item =>
      !isNaN(item.open) && !isNaN(item.high) && !isNaN(item.low) && !isNaN(item.close) && item.time > 0
    ).sort((a, b) => a.time - b.time);

    if (chartData.length === 0) {
      return { data: [], isReal: false, error: 'Data conversion failed' };
    }

    // Derive 52-week high/low from series for header display
    let fiftyTwoWeekHigh = null;
    let fiftyTwoWeekLow = null;
    if (chartData.length > 0) {
      const highs = chartData.map((d) => d.high);
      const lows = chartData.map((d) => d.low);
      fiftyTwoWeekHigh = Math.max(...highs);
      fiftyTwoWeekLow = Math.min(...lows);
    }

    return {
      data: chartData,
      isReal: true,
      fiftyTwoWeekHigh,
      fiftyTwoWeekLow,
    };
  } catch (error) {
    console.error('Error fetching stock data from backend:', error);
    const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to fetch stock data';
    
    // Return mock data as fallback
    const mockData = generateMockData(symbolUpper);
    return { data: mockData, isReal: false, error: errorMsg };
  }
}

/**
 * Fetch real-time stock price and quote information
 * Uses backend API endpoint: POST /api/v1/market-data/intraday/stocks (batch endpoint)
 * 
 * @param {string} symbol - Stock symbol
 * @returns {Promise<{price: number, change: number, changePercent: string, open: number, high: number, low: number}>}
 */
export async function fetchRealTimePrice(symbol) {
  if (!symbol || !symbol.trim()) {
    throw new Error('Symbol is required');
  }

  const symbolUpper = symbol.trim().toUpperCase();
  
  try {
    // Use batch endpoint to get latest price
    const { data } = await api.post('/api/v1/market-data/intraday/stocks', {
      symbols: [symbolUpper],
      interval: '1min',
    });

    const results = data?.results || {};
    const points = results[symbolUpper];
    
    if (!Array.isArray(points) || points.length === 0) {
      throw new Error('No price data available');
    }

    // Get first and last data points to calculate change
    const first = points[0];
    const last = points[points.length - 1];
    const open = parseFloat(first?.open || 0);
    const close = parseFloat(last?.close || 0);
    const high = parseFloat(last?.high || close);
    const low = parseFloat(last?.low || close);
    const change = close - open;
    const changePercent = open ? ((change / open) * 100).toFixed(2) + '%' : '0.00%';

    return {
      symbol: symbolUpper,
      price: Math.round(close * 100) / 100,
      open: Math.round(open * 100) / 100,
      high: Math.round(high * 100) / 100,
      low: Math.round(low * 100) / 100,
      change: Math.round(change * 100) / 100,
      changePercent,
    };
  } catch (error) {
    console.error('Error fetching real-time price:', error);
    throw error;
  }
}

/**
 * Fetch stock profile/company information
 * Note: This endpoint may need to be implemented in the backend
 * For now, returns basic info from quote data
 * 
 * @param {string} symbol - Stock symbol
 * @returns {Promise<Object>} Stock profile information
 */
export async function fetchStockInfo(symbol) {
  if (!symbol || !symbol.trim()) {
    throw new Error('Symbol is required');
  }

  const symbolUpper = symbol.trim().toUpperCase();
  
  try {
    // Use intraday endpoint to get basic info
    // In a full implementation, this would call a dedicated profile endpoint
    const { data } = await api.post('/api/v1/market-data/intraday/stocks', {
      symbols: [symbolUpper],
      interval: '1min',
    });

    const results = data?.results || {};
    const points = results[symbolUpper];
    
    if (!Array.isArray(points) || points.length === 0) {
      return {
        Symbol: symbolUpper,
        Name: `${symbolUpper} Corp`,
        Exchange: 'NASDAQ',
        Price: 0,
        Open: 0,
        High: 0,
        Low: 0,
        '52WeekHigh': null,
        '52WeekLow': null,
        AverageVolume: null,
        SharesOutstanding: null,
        MarketCapitalization: null,
        DividendYield: null,
      };
    }

    const last = points[points.length - 1];
    const first = points[0];
    const totalVolume = points.reduce((sum, p) => sum + (Number(p.volume) || 0), 0);
    const avgVolume = points.length > 0 ? Math.round(totalVolume / points.length) : null;

    return {
      Symbol: symbolUpper,
      Name: `${symbolUpper} Corp`,
      Exchange: 'NASDAQ',
      Price: parseFloat(last?.close || 0),
      Open: parseFloat(first?.open || 0),
      High: parseFloat(Math.max(...points.map((p) => Number(p.high) || 0)) || 0),
      Low: parseFloat(Math.min(...points.map((p) => Number(p.low) || 0)) || 0),
      '52WeekHigh': null,
      '52WeekLow': null,
      AverageVolume: avgVolume,
      SharesOutstanding: null,
      MarketCapitalization: null,
      DividendYield: null,
    };
  } catch (error) {
    console.error('Error fetching stock info:', error);
    return {
      Symbol: symbolUpper,
      Name: `${symbolUpper} Corp`,
      Exchange: 'NASDAQ',
      Price: 0,
      Open: 0,
      High: 0,
      Low: 0,
      '52WeekHigh': null,
      '52WeekLow': null,
      AverageVolume: null,
      SharesOutstanding: null,
      MarketCapitalization: null,
      DividendYield: null,
    };
  }
}

/**
 * Generate mock data for fallback when API fails
 * @param {string} symbol - Stock symbol
 * @returns {Array} Mock chart data
 */
function generateMockData(symbol) {
  const data = [];
  const basePrice = 100 + Math.random() * 50;
  let currentPrice = basePrice;
  const today = new Date();

  // Generate 90 days of mock data
  for (let i = 90; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const timestamp = Math.floor(date.getTime() / 1000);

    const change = (Math.random() - 0.5) * 4;
    const open = currentPrice;
    const close = open + change;
    const high = Math.max(open, close) + Math.random() * 2;
    const low = Math.min(open, close) - Math.random() * 2;

    currentPrice = close;

    data.push({
      time: timestamp,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
    });
  }

  return data;
}
