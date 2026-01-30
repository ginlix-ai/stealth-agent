import { api, headers, DEFAULT_USER_ID } from './client.js';
import * as portfolioApi from './portfolio.js';
import * as watchlistApi from './watchlist.js';
import * as watchlistItemsApi from './watchlistItems.js';

export { DEFAULT_USER_ID };

const baseURL = api.defaults.baseURL;

// --- Market data (see docs/ptc-agent-api/market data) ---

/** Index symbols: normalized (GSPC, IXIC, DJI, RUT). Index.yml / Index Batch.yml use these. */
const INDEX_SYMBOLS = ['GSPC', 'IXIC', 'DJI', 'RUT'];
const INDEX_NAMES = { GSPC: 'S&P 500', IXIC: 'NASDAQ 100', DJI: 'Dow Jones', RUT: 'Russell 2000' };

function normalizeIndexSymbol(s) {
  return String(s).replace(/^\^/, '').toUpperCase();
}

function parseDataPoints(pts, norm) {
  if (!Array.isArray(pts) || !pts.length) return null;
  const first = pts[0];
  const last = pts[pts.length - 1];
  const open = Number(first?.open ?? 0);
  const close = Number(last?.close ?? 0);
  const change = close - open;
  const changePercent = open ? (change / open) * 100 : 0;
  return {
    symbol: norm,
    name: INDEX_NAMES[norm] ?? norm,
    price: Math.round(close * 100) / 100,
    change: Math.round(change * 100) / 100,
    changePercent: Math.round(changePercent * 100) / 100,
    isPositive: change >= 0,
  };
}

function fallbackIndex(norm) {
  return {
    symbol: norm,
    name: INDEX_NAMES[norm] ?? norm,
    price: 0,
    change: 0,
    changePercent: 0,
    isPositive: true,
  };
}

/**
 * GET /api/v1/market-data/intraday/indexes/:symbol (Index.yml)
 * Path uses normalized symbol (e.g. GSPC). Query: interval, from, to optional.
 */
export async function getIndex(symbol, opts = {}) {
  const { interval = '1min', from: fromDate, to: toDate } = opts;
  const norm = normalizeIndexSymbol(String(symbol).trim());
  try {
    const params = { interval };
    if (fromDate) params.from = fromDate;
    if (toDate) params.to = toDate;
    const { data } = await api.get(`/api/v1/market-data/intraday/indexes/${encodeURIComponent(norm)}`, {
      params,
    });
    const pts = data?.data ?? [];
    const out = parseDataPoints(pts, data?.symbol ?? norm);
    if (!out) throw new Error(`No intraday data for ${norm}`);
    return out;
  } catch (e) {
    const msg = e.response?.data?.detail ?? e.message;
    throw new Error(typeof msg === 'string' ? msg : String(msg));
  }
}

/**
 * POST /api/v1/market-data/intraday/indexes (Index Batch.yml)
 * Body: { symbols: ["GSPC","DJI","IXIC"], interval?, from?, to? }. Returns { indices, failedCount }.
 */
export async function getIndices(symbols = INDEX_SYMBOLS, opts = {}) {
  const { interval = '1min', from: fromDate, to: toDate } = opts;
  const list = symbols.map((s) => normalizeIndexSymbol(String(s).trim()));
  try {
    const body = { symbols: list, interval };
    if (fromDate) body.from = fromDate;
    if (toDate) body.to = toDate;
    const { data } = await api.post('/api/v1/market-data/intraday/indexes', body);
    const results = data?.results ?? {};
    const errors = data?.errors ?? {};
    const indices = list.map((norm) => {
      const pts = results[norm];
      const out = parseDataPoints(pts, norm);
      return out ?? fallbackIndex(norm);
    });
    const failed = list.filter(
      (norm) => errors[norm] || !(Array.isArray(results[norm]) && results[norm].length)
    ).length;
    return { indices, failedCount: failed };
  } catch (e) {
    const msg = e.response?.data?.detail ?? e.message;
    throw new Error(typeof msg === 'string' ? msg : String(msg));
  }
}

export { INDEX_NAMES, INDEX_SYMBOLS, fallbackIndex, normalizeIndexSymbol };

// --- Hello ---

export async function fetchHello() {
  const { data } = await api.get('/hello', { responseType: 'text' });
  return data;
}

// --- Users ---

export async function createUser(userData, userId = DEFAULT_USER_ID) {
  const { data } = await api.post('/api/v1/users', userData, { headers: headers(userId) });
  return data;
}

export async function getCurrentUser(userId = DEFAULT_USER_ID) {
  const { data } = await api.get('/api/v1/users/me', { headers: headers(userId) });
  return data;
}

export async function getPreferences(userId = DEFAULT_USER_ID) {
  const { data } = await api.get('/api/v1/users/me/preferences', { headers: headers(userId) });
  return data;
}

export async function updateCurrentUser(userData, userId = DEFAULT_USER_ID) {
  const { data } = await api.put('/api/v1/users/me', userData, { headers: headers(userId) });
  return data;
}

export async function updatePreferences(preferences, userId = DEFAULT_USER_ID) {
  const { data } = await api.put('/api/v1/users/me/preferences', preferences, { headers: headers(userId) });
  return data;
}

// --- Watchlist & Watchlist Items (CRUD) ---

export const listWatchlists = watchlistApi.listWatchlists;
export const createWatchlist = watchlistApi.createWatchlist;
export const updateWatchlist = watchlistApi.updateWatchlist;
export const deleteWatchlist = watchlistApi.deleteWatchlist;
export const listWatchlistItems = watchlistItemsApi.listWatchlistItems;
export const updateWatchlistItem = watchlistItemsApi.updateWatchlistItem;

export async function getWatchlistItems(userId = DEFAULT_USER_ID) {
  return watchlistItemsApi.listWatchlistItems('default', userId);
}

export async function addWatchlistItem(symbol, userId = DEFAULT_USER_ID) {
  return watchlistItemsApi.addWatchlistItem(
    'default',
    { symbol: String(symbol).trim().toUpperCase(), instrument_type: 'stock' },
    userId
  );
}

export async function deleteWatchlistItem(itemId, userId = DEFAULT_USER_ID) {
  return watchlistItemsApi.deleteWatchlistItem('default', itemId, userId);
}

// --- Stock prices (batch, for watchlist) ---

const DEFAULT_WATCHLIST_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA'];
const DEFAULT_WATCHLIST_NAMES = { AAPL: 'Apple', MSFT: 'Microsoft', NVDA: 'NVIDIA', AMZN: 'Amazon', TSLA: 'Tesla' };

export { DEFAULT_WATCHLIST_SYMBOLS, DEFAULT_WATCHLIST_NAMES };

/**
 * Get company names for a list of stock symbols (FMP profile companyName).
 * @param {string[]} symbols - e.g. ['AAPL', 'MSFT']
 * @returns {Promise<Record<string, string>>} symbol -> company name
 */
export async function getStockCompanyNames(symbols) {
  const list = [...(symbols || [])].map((s) => String(s).trim().toUpperCase()).filter(Boolean);
  if (!list.length) return {};
  try {
    const { data } = await api.post('/api/v1/market-data/stocks/names', { symbols: list });
    return data?.names ?? {};
  } catch {
    return {};
  }
}

export async function getStockPrices(symbols) {
  const list = [...(symbols || [])].map((s) => String(s).trim().toUpperCase()).filter(Boolean);
  if (!list.length) return [];
  try {
    const { data } = await api.post('/api/v1/market-data/intraday/stocks', { symbols: list, interval: '1min' });
    const results = data?.results ?? {};
    return list.map((sym) => {
      const pts = results[sym];
      if (!Array.isArray(pts) || !pts.length) return { symbol: sym, price: 0, change: 0, changePercent: 0, isPositive: true };
      const first = pts[0];
      const last = pts[pts.length - 1];
      const open = Number(first?.open ?? 0);
      const close = Number(last?.close ?? 0);
      const change = close - open;
      const pct = open ? (change / open) * 100 : 0;
      return {
        symbol: sym,
        price: Math.round(close * 100) / 100,
        change: Math.round(change * 100) / 100,
        changePercent: Math.round(pct * 100) / 100,
        isPositive: change >= 0,
      };
    });
  } catch {
    return list.map((sym) => ({ symbol: sym, price: 0, change: 0, changePercent: 0, isPositive: true }));
  }
}

// --- Portfolio (use CRUD module) ---

export const listPortfolio = portfolioApi.listPortfolio;
export const updatePortfolioHolding = portfolioApi.updatePortfolioHolding;
export const deletePortfolioHolding = portfolioApi.deletePortfolioHolding;

export const getPortfolio = portfolioApi.listPortfolio;

/** Add portfolio holding. Payload: symbol, instrument_type, quantity, average_cost?, ... */
export const addPortfolioHolding = portfolioApi.addPortfolioHolding;

// --- Workspaces ---

export async function getWorkspaces(userId = DEFAULT_USER_ID, limit = 20, offset = 0) {
  const { data } = await api.get('/api/v1/workspaces', {
    params: { limit, offset },
    headers: headers(userId),
  });
  return data;
}

export async function createWorkspace(name, description = '', config = {}, userId = DEFAULT_USER_ID) {
  const { data } = await api.post('/api/v1/workspaces', { name, description, config }, { headers: headers(userId) });
  return data;
}

export async function deleteWorkspace(workspaceId) {
  if (!workspaceId) throw new Error('Workspace ID is required');
  const id = String(workspaceId).trim();
  if (!id) throw new Error('Workspace ID cannot be empty');
  await api.delete(`/api/v1/workspaces/${id}`);
}

export async function getOrCreateWorkspace(userId = DEFAULT_USER_ID) {
  const data = await getWorkspaces(userId, 1, 0);
  if (data.workspaces?.length) return data.workspaces[0].workspace_id;
  const ws = await createWorkspace('Default Workspace', 'Default workspace for chat', {}, userId);
  return ws.workspace_id;
}

// --- Conversations ---

export async function getConversations(userId = DEFAULT_USER_ID, limit = 50, offset = 0) {
  const { data } = await api.get('/api/v1/conversations', {
    params: { limit, offset },
    headers: headers(userId),
  });
  return data;
}

// --- Streaming (fetch + ReadableStream; axios not used) ---

async function streamFetch(url, opts, onEvent) {
  const res = await fetch(`${baseURL}${url}`, opts);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let ev = {};
  const processLine = (line) => {
    if (line.startsWith('id: ')) ev.id = line.slice(4).trim();
    else if (line.startsWith('event: ')) ev.event = line.slice(7).trim();
    else if (line.startsWith('data: ')) {
      try {
        const d = JSON.parse(line.slice(6));
        if (ev.event) d.event = ev.event;
        onEvent(d);
      } catch (e) {
        console.warn('[api] SSE parse error', e, line);
      }
      ev = {};
    } else if (line.trim() === '') ev = {};
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    lines.forEach(processLine);
  }
  buffer.split('\n').forEach(processLine);
}

export async function replayThreadHistory(threadId, onEvent = () => {}) {
  if (!threadId) throw new Error('Thread ID is required');
  await streamFetch(`/api/v1/threads/${threadId}/replay`, { method: 'GET' }, onEvent);
}

export async function sendChatMessageStream(
  message,
  workspaceId,
  threadId = '__default__',
  messageHistory = [],
  planMode = false,
  onEvent = () => {},
  userId = DEFAULT_USER_ID
) {
  const messages = [...messageHistory, { role: 'user', content: message }];
  await streamFetch(
    '/api/v1/chat/stream',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...headers(userId) },
      body: JSON.stringify({ workspace_id: workspaceId, thread_id: threadId, messages, plan_mode: planMode }),
    },
    onEvent
  );
}
