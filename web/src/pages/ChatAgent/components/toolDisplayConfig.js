import {
  TrendingUp, Building2, BarChart3, PieChart, Search, Globe,
  FilePlus, FileText, FilePen, FolderSearch, SquareChevronRight, Wrench,
  Newspaper, Brain, User, FileBarChart, Clock, ClipboardList, Zap, Settings, Terminal,
} from 'lucide-react';

export const TOOL_DISPLAY_CONFIG = {
  // Market Data
  get_stock_daily_prices:   { displayName: 'Stock Prices',         i18nKey: 'stockPrices',         icon: TrendingUp },
  get_company_overview:     { displayName: 'Company Overview',     i18nKey: 'companyOverview',     icon: Building2 },
  get_market_indices:       { displayName: 'Market Indices',       i18nKey: 'marketIndices',       icon: BarChart3 },
  get_sector_performance:   { displayName: 'Sector Performance',   i18nKey: 'sectorPerformance',   icon: PieChart },
  screen_stocks:            { displayName: 'Stock Screener',       i18nKey: 'stockScreener',       icon: Search },
  // SEC
  get_sec_filing:           { displayName: 'SEC Filing',           i18nKey: 'secFiling',           icon: FileBarChart },
  // Web search / news
  get_entity_news:          { displayName: 'Entity News',          i18nKey: 'entityNews',          icon: Newspaper },
  search_tickers:           { displayName: 'Ticker Search',        i18nKey: 'tickerSearch',        icon: Search },
  // Fundamentals (MCP)
  get_financial_statements: { displayName: 'Financial Statements', i18nKey: 'financialStatements', icon: FileBarChart },
  get_financial_ratios:     { displayName: 'Financial Ratios',     i18nKey: 'financialRatios',     icon: FileBarChart },
  get_growth_metrics:       { displayName: 'Growth Metrics',       i18nKey: 'growthMetrics',       icon: TrendingUp },
  get_historical_valuation: { displayName: 'Valuation History',    i18nKey: 'valuationHistory',    icon: BarChart3 },
  // Price Data (MCP)
  get_stock_data:           { displayName: 'Stock Data',           i18nKey: 'stockData',           icon: TrendingUp },
  get_asset_data:           { displayName: 'Asset Data',           i18nKey: 'assetData',           icon: TrendingUp },
  // User Data
  get_user_data:            { displayName: 'User Data',            i18nKey: 'userData',            icon: User },
  update_user_data:         { displayName: 'Update Data',          i18nKey: 'updateData',          icon: User },
  remove_user_data:         { displayName: 'Remove Data',          i18nKey: 'removeData',          icon: User },
  // Core tools
  Bash:                     { displayName: 'Bash',                 i18nKey: 'bash',                icon: Terminal },
  Glob:                     { displayName: 'Glob',                 i18nKey: 'glob',                icon: FolderSearch },
  Grep:                     { displayName: 'Grep',                 i18nKey: 'grep',                icon: Search },
  WebSearch:                { displayName: 'Web Search',           i18nKey: 'webSearch',           icon: Globe },
  WebFetch:                 { displayName: 'Web Fetch',            i18nKey: 'webFetch',            icon: Newspaper },
  Write:                    { displayName: 'Write',                i18nKey: 'write',               icon: FilePlus },
  Read:                     { displayName: 'Read',                 i18nKey: 'read',                icon: FileText },
  Edit:                     { displayName: 'Edit',                 i18nKey: 'edit',                icon: FilePen },
  ExecuteCode:              { displayName: 'Execute Code',         i18nKey: 'executeCode',         icon: SquareChevronRight },
  think_tool:               { displayName: 'Thinking',             i18nKey: 'thinking',            icon: Brain },
  // Background subagent management
  Wait:                     { displayName: 'Waiting for Subagent', i18nKey: 'waitingForSubagent',  icon: Clock },
  TaskOutput:               { displayName: 'Task Output',          i18nKey: 'taskOutput',          icon: ClipboardList },
  // Automations
  check_automations:        { displayName: 'Automations',          i18nKey: 'automations',         icon: Clock },
  create_automation:        { displayName: 'Create Automation',    i18nKey: 'createAutomation',    icon: Zap },
  manage_automation:        { displayName: 'Manage Automation',    i18nKey: 'manageAutomation',    icon: Settings },
};

export function getDisplayName(rawToolName, t) {
  const config = TOOL_DISPLAY_CONFIG[rawToolName];
  if (t && config?.i18nKey) return t(`toolArtifact.tool.${config.i18nKey}`);
  return config?.displayName || rawToolName;
}

export function getToolIcon(rawToolName) {
  return TOOL_DISPLAY_CONFIG[rawToolName]?.icon || Wrench;
}

export function getInProgressText(rawToolName, toolCall, t) {
  const args = toolCall?.args;
  const tr = t ? (key, opts) => t(`toolArtifact.inProgress.${key}`, opts) : null;
  switch (rawToolName) {
    case 'get_stock_daily_prices':
      return args?.symbol
        ? (tr?.('fetchingSymbolPrices', { symbol: args.symbol }) ?? `fetching ${args.symbol} prices...`)
        : (tr?.('fetchingPrices') ?? 'fetching prices...');
    case 'get_company_overview':
      return args?.symbol
        ? (tr?.('analyzingSymbol', { symbol: args.symbol }) ?? `analyzing ${args.symbol}...`)
        : (tr?.('analyzing') ?? 'analyzing...');
    case 'get_market_indices':
      return tr?.('fetchingMarketIndices') ?? 'fetching market indices...';
    case 'get_sector_performance':
      return tr?.('fetchingSectorData') ?? 'fetching sector data...';
    case 'screen_stocks':
      return tr?.('screeningStocks') ?? 'screening stocks...';
    case 'get_sec_filing':
      return args?.symbol
        ? (tr?.('fetchingSymbolFiling', { symbol: args.symbol }) ?? `fetching ${args.symbol} filing...`)
        : (tr?.('fetchingFiling') ?? 'fetching filing...');
    case 'Glob': {
      const pattern = args?.pattern;
      return pattern
        ? (tr?.('searchingPattern', { pattern }) ?? `searching '${pattern}'...`)
        : (tr?.('searching') ?? 'searching...');
    }
    case 'Grep': {
      const pattern = args?.pattern;
      return pattern
        ? (tr?.('searchingForPattern', { pattern }) ?? `searching for '${pattern}'...`)
        : (tr?.('searching') ?? 'searching...');
    }
    case 'WebSearch': {
      const query = args?.query;
      return query
        ? (tr?.('searchingQuery', { query }) ?? `searching '${query}'...`)
        : (tr?.('searching') ?? 'searching...');
    }
    case 'WebFetch': {
      try {
        const domain = args?.url ? new URL(args.url).hostname : null;
        return domain
          ? (tr?.('fetchingDomain', { domain }) ?? `fetching ${domain}...`)
          : (tr?.('fetching') ?? 'fetching...');
      } catch {
        return tr?.('fetching') ?? 'fetching...';
      }
    }
    case 'Write': {
      const fp = args?.file_path || args?.filePath || '';
      const name = fp.split('/').pop();
      return name
        ? (tr?.('writingFile', { name }) ?? `writing ${name}...`)
        : (tr?.('writing') ?? 'writing...');
    }
    case 'Read': {
      const fp = args?.file_path || args?.filePath || '';
      const name = fp.split('/').pop();
      return name
        ? (tr?.('readingFile', { name }) ?? `reading ${name}...`)
        : (tr?.('reading') ?? 'reading...');
    }
    case 'Edit': {
      const fp = args?.file_path || args?.filePath || '';
      const name = fp.split('/').pop();
      return name
        ? (tr?.('editingFile', { name }) ?? `editing ${name}...`)
        : (tr?.('editing') ?? 'editing...');
    }
    case 'Bash':
      return args?.description ? `${args.description}...` : (tr?.('runningCommand') ?? 'running command...');
    case 'ExecuteCode':
      return args?.description ? `${args.description}...` : (tr?.('executing') ?? 'executing...');
    case 'Wait':
      return tr?.('waitingForSubagent') ?? 'waiting for subagent...';
    case 'TaskOutput':
      return tr?.('fetchingTaskOutput') ?? 'fetching task output...';
    case 'check_automations':
      return tr?.('checkingAutomations') ?? 'checking automations...';
    case 'create_automation':
      return args?.name
        ? (tr?.('creatingName', { name: args.name }) ?? `creating ${args.name}...`)
        : (tr?.('creatingAutomation') ?? 'creating automation...');
    case 'manage_automation':
      return args?.action
        ? (tr?.('actionAutomation', { action: args.action }) ?? `${args.action} automation...`)
        : (tr?.('managingAutomation') ?? 'managing automation...');
    default:
      return tr?.('processing') ?? 'processing...';
  }
}

/**
 * Extracts a short completed-state summary from tool call args.
 * Used in both live zone (completed but not yet in accordion) and accordion rows.
 */
export function getCompletedSummary(toolName, toolCall) {
  const args = toolCall?.args;
  if (!args) return null;
  if (args.description) return args.description;
  if (args.symbol) return args.symbol;
  if (args.query) return args.query;
  if (args.pattern) return args.pattern;
  if (args.url) {
    try {
      return new URL(args.url).hostname;
    } catch {
      return args.url;
    }
  }
  if (args.file_path || args.filePath) {
    const fp = args.file_path || args.filePath;
    return fp.split('/').pop() || null;
  }
  return null;
}

function formatByteSize(bytes, t) {
  if (bytes < 100) return null;
  if (bytes < 1000) {
    return t ? t('toolArtifact.nChars', { count: bytes }) : `~${bytes} chars`;
  }
  const size = (bytes / 1000).toFixed(1);
  return t ? t('toolArtifact.nKB', { size }) : `~${size} KB`;
}

export function getPreparingText(toolName, argsLength, t) {
  const size = formatByteSize(argsLength, t);
  const sizeLabel = size ? ` (${size})` : '';
  const tr = t ? (key, opts) => t(`toolArtifact.preparing.${key}`, opts) : null;

  switch (toolName) {
    case 'Write':
      return tr?.('writingCode', { size: sizeLabel }) ?? `writing code${sizeLabel}...`;
    case 'Edit':
      return tr?.('composingEdits', { size: sizeLabel }) ?? `composing edits${sizeLabel}...`;
    case 'Bash':
      return tr?.('preparingCommand', { size: sizeLabel }) ?? `preparing command${sizeLabel}...`;
    case 'ExecuteCode':
      return tr?.('composingCode', { size: sizeLabel }) ?? `composing code${sizeLabel}...`;
    case 'WebSearch':
      return tr?.('craftingSearch') ?? 'crafting search...';
    case 'WebFetch':
      return tr?.('preparingRequest') ?? 'preparing request...';
    case 'Grep':
      return tr?.('buildingSearchPattern') ?? 'building search pattern...';
    default:
      return tr?.('generating', { size: sizeLabel }) ?? `generating${sizeLabel}...`;
  }
}

/**
 * Detects if a tool result was truncated due to size and saved to filesystem.
 * Returns { isTruncated, filePath, preview } or { isTruncated: false }.
 */
export function parseTruncatedResult(content) {
  if (!content || typeof content !== 'string') return { isTruncated: false };

  if (!content.startsWith('Tool result too large')) return { isTruncated: false };

  // Extract the filesystem path
  const pathMatch = content.match(/saved in the filesystem at this path:\s*(\/large_tool_results\/\S+)/);
  const filePath = pathMatch?.[1] || null;

  // Extract the preview (everything after the "head and tail" intro line)
  const previewMatch = content.match(/indicate omitted lines in the middle of the content\):\n\n([\s\S]*)$/);
  const rawPreview = previewMatch?.[1]?.trim() || '';

  return { isTruncated: true, filePath, preview: rawPreview };
}

/**
 * Strips `cat -n` style line number prefixes from content.
 * Matches lines like "     1\t..." or "  123\t..." and removes the prefix.
 * Only strips if the majority of lines match the pattern (to avoid false positives).
 */
export function stripLineNumbers(content) {
  if (!content || typeof content !== 'string') return content;

  const lines = content.split('\n');
  // Check if content has line number prefixes: spaces + digits + tab
  const lineNumPattern = /^\s*\d+\t/;
  const matchCount = lines.filter((l) => lineNumPattern.test(l)).length;

  // Only strip if >50% of non-empty lines match the pattern
  const nonEmptyLines = lines.filter((l) => l.trim().length > 0).length;
  if (nonEmptyLines === 0 || matchCount / nonEmptyLines < 0.5) return content;

  return lines
    .map((line) => line.replace(lineNumPattern, ''))
    .join('\n');
}
