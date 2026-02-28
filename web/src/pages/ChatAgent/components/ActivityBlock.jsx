import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, ChevronDown, Wrench } from 'lucide-react';
import { getDisplayName, getToolIcon, getInProgressText, getPreparingText, getCompletedSummary } from './toolDisplayConfig';
import { TextShimmer } from '@/components/ui/text-shimmer';
import { DotLoader } from '@/components/ui/dot-loader';
import { useAnimatedText } from '@/components/ui/animated-text';
import Markdown from './Markdown';
import {
  INLINE_ARTIFACT_TOOLS,
  InlineStockPriceCard,
  InlineCompanyOverviewCard,
  InlineMarketIndicesCard,
  InlineSectorPerformanceCard,
  InlineSecFilingCard,
  InlineStockScreenerCard,
} from './charts/InlineMarketCharts';
import { InlineAutomationCard } from './charts/InlineAutomationCards';
import { useTranslation } from 'react-i18next';

/** Tool names where clicking should open the file in the FilePanel */
const FILE_NAV_TOOLS = new Set(['Read', 'Write', 'Save', 'read_file', 'write_file', 'save_file']);

function getFilePathFromArgs(args) {
  if (!args) return null;
  return args.file_path || args.filePath || args.path || args.filename || null;
}

/** Map artifact type → inline chart component */
const INLINE_ARTIFACT_MAP = {
  stock_prices: InlineStockPriceCard,
  company_overview: InlineCompanyOverviewCard,
  market_indices: InlineMarketIndicesCard,
  sector_performance: InlineSectorPerformanceCard,
  sec_filing: InlineSecFilingCard,
  stock_screener: InlineStockScreenerCard,
  automations: InlineAutomationCard,
};

/** Spring config matching radix-accordion feel */
const SPRING = { type: 'spring', stiffness: 150, damping: 17 };
const SPRING_SNAPPY = { type: 'spring', stiffness: 200, damping: 22 };

/**
 * ActivityBlock — unified component for completed + live activity items.
 *
 * Replaces the old ActivityAccordion + LiveActivity two-component architecture.
 * Items move from the live zone to the accordion zone in the same React render,
 * eliminating the visible gap caused by fade-out/reappear across render cycles.
 *
 * Uses framer-motion spring animations for smooth accordion expand/collapse,
 * item entrance/exit, and chevron rotation.
 */
function ActivityBlock({ items, preparingToolCall, isStreaming, onToolCallClick, onOpenFile }) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const prevCompletedIdsRef = useRef(new Set());

  // Partition items into zones
  const completedItems = [];
  const liveItems = [];
  const inlineChartItems = [];

  for (const item of items) {
    if (item._liveState === 'completed') {
      if (
        item.type === 'tool_call' &&
        INLINE_ARTIFACT_TOOLS.has(item.toolName || '') &&
        item.toolCallResult?.artifact
      ) {
        inlineChartItems.push(item);
      } else {
        completedItems.push(item);
      }
    } else {
      liveItems.push(item);
    }
  }

  // Detect newly completed items for entrance animation
  const currentCompletedIds = new Set(completedItems.map(i => i.id || i.toolCallId));
  const newlyCompletedIds = new Set();
  if (isStreaming) {
    for (const id of currentCompletedIds) {
      if (!prevCompletedIdsRef.current.has(id)) {
        newlyCompletedIds.add(id);
      }
    }
  }
  prevCompletedIdsRef.current = currentCompletedIds;

  const hasInlineCharts = inlineChartItems.length > 0;
  const hasCompleted = completedItems.length > 0;
  const hasLive = liveItems.length > 0;
  const hasPreparingTools = !!preparingToolCall;

  if (!hasInlineCharts && !hasCompleted && !hasLive && !hasPreparingTools) return null;

  // Build accordion summary label
  const reasoningCount = completedItems.filter(i => i.type === 'reasoning').length;
  const toolCallCount = completedItems.filter(i => i.type === 'tool_call').length;
  let summaryLabel;
  if (reasoningCount > 0 && toolCallCount > 0) {
    const parts = [];
    if (reasoningCount > 0) parts.push(t('toolArtifact.nReasoning', { count: reasoningCount }));
    if (toolCallCount > 0) parts.push(t('toolArtifact.nToolCalls', { count: toolCallCount }));
    summaryLabel = parts.join(' · ');
  } else if (completedItems.length > 0) {
    summaryLabel = t('toolArtifact.nStepsCompleted', { count: completedItems.length });
  }

  return (
    <div className="mt-1 mb-1">
      {/* Inline chart cards — always visible, above accordion */}
      {hasInlineCharts && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: hasCompleted || hasLive || hasPreparingTools ? 6 : 0 }}>
          {inlineChartItems.map((item, idx) => {
            const artifact = item.toolCallResult.artifact;
            const ChartComponent = INLINE_ARTIFACT_MAP[artifact.type];
            if (!ChartComponent) return null;
            return (
              <div key={`chart-${item.id || idx}`}>
                <ChartComponent
                  artifact={artifact}
                  onClick={() => onToolCallClick?.(item)}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Accordion zone (top) — completed items, animates in smoothly */}
      <AnimatePresence initial={false}>
        {hasCompleted && (
          <motion.div
            key="accordion-zone"
            initial={{ opacity: 0, height: 0, overflow: 'hidden' }}
            animate={{ opacity: 1, height: 'auto', overflow: 'visible' }}
            transition={SPRING_SNAPPY}
          >
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-2 transition-colors hover:bg-foreground/5 w-full rounded-md"
              style={{
                padding: '5px 10px',
                fontSize: '13px',
                color: 'var(--Labels-Tertiary)',
              }}
            >
              <motion.div
                animate={{ rotate: isExpanded ? 90 : 0 }}
                transition={SPRING}
                className="flex-shrink-0"
              >
                <ChevronDown className="h-3.5 w-3.5 -rotate-90" />
              </motion.div>
              <span>{summaryLabel}</span>
            </button>

            <AnimatePresence initial={false}>
              {isExpanded && (
                <motion.div
                  key="accordion-body"
                  initial={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
                  animate={{ height: 'auto', opacity: 1, '--mask-stop': '100%', overflow: 'visible' }}
                  exit={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
                  transition={SPRING}
                  style={{
                    maskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
                    WebkitMaskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
                  }}
                >
                  <div
                    className="mt-1 ml-2 space-y-0.5 rounded-md"
                    style={{
                      borderLeft: '2px solid var(--color-border-muted)',
                      padding: '4px 0',
                    }}
                  >
                    {completedItems.map((item, idx) => {
                      const itemId = item.id || item.toolCallId;
                      const isNew = newlyCompletedIds.has(itemId);
                      const itemKey = item.type === 'reasoning' ? `r-${itemId || idx}` : `t-${itemId || idx}`;

                      const content = renderCompletedItem(item, idx, onToolCallClick, onOpenFile);
                      if (!content) return null;

                      if (isNew) {
                        return (
                          <motion.div
                            key={itemKey}
                            initial={{ opacity: 0, height: 0, overflow: 'hidden' }}
                            animate={{ opacity: 1, height: 'auto', overflow: 'visible' }}
                            transition={SPRING_SNAPPY}
                          >
                            {content}
                          </motion.div>
                        );
                      }

                      return <div key={itemKey}>{content}</div>;
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live zone (bottom) — active/completing items + preparing */}
      <AnimatePresence initial={false}>
        {(hasLive || hasPreparingTools) && (
          <motion.div
            key="live-zone"
            className="mt-2 space-y-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, height: 0, marginTop: 0, overflow: 'hidden' }}
            transition={SPRING_SNAPPY}
          >
            {/* Live items in chronological order */}
            <AnimatePresence initial={false}>
              {liveItems.map(item => {
                if (item.type === 'reasoning') {
                  return (
                    <motion.div
                      key={`live-r-${item.id}`}
                      initial={{ opacity: 0, height: 0, overflow: 'hidden' }}
                      animate={{ opacity: item._liveState === 'completing' ? 0.6 : 1, height: 'auto', overflow: 'visible' }}
                      exit={{ opacity: 0, height: 0, overflow: 'hidden', paddingTop: 0, paddingBottom: 0 }}
                      transition={SPRING}
                      className="px-3"
                      style={{ paddingTop: '8px', paddingBottom: '8px' }}
                    >
                      <div
                        className="flex items-center gap-2 mb-1"
                        style={{ fontSize: '13px', color: 'var(--Labels-Secondary)' }}
                      >
                        <Brain className="h-4 w-4 flex-shrink-0" />
                        {item._liveState === 'active' ? (
                          <TextShimmer
                            as="span"
                            className="font-medium truncate text-[13px] [--base-color:var(--Labels-Secondary)] [--base-gradient-color:var(--color-text-primary)]"
                            duration={1.5}
                          >
                            {item.reasoningTitle
                              ? t('toolArtifact.reasoningLabel', { title: item.reasoningTitle })
                              : t('toolArtifact.reasoningPending')}
                          </TextShimmer>
                        ) : (
                          <span className="font-medium truncate">{t('toolArtifact.reasoningComplete')}</span>
                        )}
                      </div>

                      {item.content && (
                        <AnimatedReasoningContent
                          content={item.content}
                          isStreaming={item._liveState === 'active'}
                        />
                      )}
                    </motion.div>
                  );
                }
                if (item.type === 'tool_call') {
                  return (
                    <motion.div
                      key={`live-t-${item.id || item.toolCallId}`}
                      initial={{ opacity: 0, height: 0, overflow: 'hidden' }}
                      animate={{ opacity: 1, height: 'auto', overflow: 'visible' }}
                      exit={{ opacity: 0, height: 0, overflow: 'hidden' }}
                      transition={SPRING_SNAPPY}
                    >
                      <ToolCallLiveRow tc={item} liveState={item._liveState} />
                    </motion.div>
                  );
                }
                return null;
              })}
            </AnimatePresence>

            {/* Preparing tool call — always at the bottom */}
            <AnimatePresence initial={false}>
              {hasPreparingTools && (
                <motion.div
                  key="preparing"
                  initial={{ opacity: 0, height: 0, overflow: 'hidden' }}
                  animate={{ opacity: 1, height: 'auto', overflow: 'visible' }}
                  exit={{ opacity: 0, height: 0, overflow: 'hidden' }}
                  transition={SPRING_SNAPPY}
                >
                  <PreparingToolCallRow tc={preparingToolCall} />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Renders a single completed item (reasoning or tool_call) for the accordion body */
function renderCompletedItem(item, idx, onToolCallClick, onOpenFile) {
  if (item.type === 'reasoning') {
    return <ReasoningRow item={item} />;
  }
  if (item.type === 'tool_call') {
    const toolName = item.toolName || '';

    if (toolName === 'Edit' || toolName === 'edit_file') {
      return <EditToolRow item={item} onOpenFile={onOpenFile} />;
    }

    if (FILE_NAV_TOOLS.has(toolName)) {
      const filePath = getFilePathFromArgs(item.toolCall?.args);
      return (
        <ToolCallRow
          item={item}
          onClick={() => {
            if (filePath && onOpenFile) {
              onOpenFile(filePath);
            } else {
              onToolCallClick?.(item);
            }
          }}
        />
      );
    }

    return (
      <ToolCallRow
        item={item}
        onClick={() => onToolCallClick?.(item)}
      />
    );
  }
  return null;
}

/** Animated reasoning content — smoothly reveals text during streaming */
function AnimatedReasoningContent({ content, isStreaming }) {
  const displayText = useAnimatedText(content || '', { enabled: isStreaming });
  return (
    <Markdown
      variant="compact"
      content={displayText}
      className="text-xs"
      style={{ opacity: 0.8 }}
    />
  );
}

/** Live tool call row — shows active or completing state */
function ToolCallLiveRow({ tc, liveState }) {
  const { t } = useTranslation();
  const toolName = tc.toolName || '';
  const displayName = getDisplayName(toolName, t);
  const IconComponent = getToolIcon(toolName);
  const isInProgress = liveState === 'active' && !tc.isComplete && !tc._recentlyCompleted;
  const progressText = isInProgress ? getInProgressText(toolName, tc.toolCall, t) : null;

  return (
    <motion.div
      className="flex items-center gap-2 px-3 rounded-md"
      animate={{
        backgroundColor: isInProgress ? 'var(--color-accent-soft)' : 'var(--color-border-muted)',
        opacity: isInProgress ? 1 : 0.6,
      }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{
        border: '1px solid var(--color-border-muted)',
        fontSize: '13px',
        color: 'var(--Labels-Secondary)',
        paddingTop: '6px',
        paddingBottom: '6px',
      }}
    >
      <div className="relative flex-shrink-0">
        <IconComponent className="h-4 w-4" />
        <AnimatePresence>
          {!isInProgress && (
            <motion.span
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={SPRING_SNAPPY}
              className="h-3 w-3 absolute -top-0.5 -right-0.5 flex items-center justify-center"
              style={{ color: 'var(--color-profit-muted)' }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      {isInProgress ? (
        <TextShimmer
          as="span"
          className="font-medium text-[13px] [--base-color:var(--Labels-Secondary)] [--base-gradient-color:var(--color-text-primary)]"
          duration={1.5}
        >
          {`${displayName} ${progressText || ''}`}
        </TextShimmer>
      ) : (
        <>
          <span className="font-medium flex-shrink-0 whitespace-nowrap">{displayName}</span>
          {(() => {
            const summary = getCompletedSummary(toolName, tc.toolCall);
            return summary
              ? <span className="truncate min-w-0" style={{ opacity: 0.55 }}>— {summary}</span>
              : <span style={{ opacity: 0.55 }}>{t('toolArtifact.done')}</span>;
          })()}
        </>
      )}
    </motion.div>
  );
}

/** Preparing row — shown while tool_call_chunks are still streaming */
function PreparingToolCallRow({ tc }) {
  const { t } = useTranslation();
  const toolName = tc.toolName || '';
  const displayName = toolName ? getDisplayName(toolName, t) : t('toolArtifact.toolCall');
  const IconComponent = toolName ? getToolIcon(toolName) : Wrench;
  const prepText = getPreparingText(toolName, tc.argsLength, t);

  return (
    <div
      className="flex items-center gap-2 px-3"
      style={{
        fontSize: '13px',
        color: 'var(--Labels-Secondary)',
        padding: '6px 12px',
        opacity: 0.85,
      }}
    >
      <DotLoader
        className="flex-shrink-0 gap-px"
        dotClassName="bg-foreground/15 [&.active]:bg-foreground size-[1.5px]"
      />
      <IconComponent className="h-4 w-4 flex-shrink-0" />
      <span className="font-medium">{displayName}</span>
      <span style={{ opacity: 0.55 }}>{prepText}</span>
    </div>
  );
}

/* --- Accordion sub-components --- */

function ReasoningRow({ item }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const title = item.reasoningTitle ? t('toolArtifact.reasoningLabel', { title: item.reasoningTitle }) : t('toolArtifact.reasoning');
  const hasContent = !!item.content;

  return (
    <div>
      <button
        onClick={() => hasContent && setExpanded(!expanded)}
        className={`flex items-center gap-2 px-3 py-1 w-full text-left rounded ${hasContent ? 'transition-colors hover:bg-foreground/5 cursor-pointer' : ''}`}
        style={{ fontSize: '13px', color: 'var(--Labels-Tertiary)' }}
      >
        <Brain className="h-3.5 w-3.5 flex-shrink-0" style={{ opacity: 0.7 }} />
        <span className="truncate">{title}</span>
        {hasContent && (
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={SPRING}
            className="ml-auto flex-shrink-0"
          >
            <ChevronDown className="h-3 w-3" style={{ opacity: 0.5 }} />
          </motion.div>
        )}
      </button>
      <AnimatePresence initial={false}>
        {expanded && item.content && (
          <motion.div
            key="reasoning-content"
            initial={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
            animate={{ height: 'auto', opacity: 1, '--mask-stop': '100%', overflow: 'visible' }}
            exit={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
            transition={SPRING}
            style={{
              maskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
              WebkitMaskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
            }}
          >
            <Markdown
              variant="compact"
              content={item.content}
              className="ml-3 pl-3 pr-2 py-1 text-xs"
              style={{ borderLeft: '2px solid var(--color-accent-overlay)' }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ToolCallRow({ item, onClick }) {
  const { t } = useTranslation();
  const toolName = item.toolName || '';
  const displayName = getDisplayName(toolName, t);
  const IconComponent = getToolIcon(toolName);

  const summary = getCompletedSummary(toolName, item.toolCall) || '';

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-1 w-full text-left transition-colors hover:bg-foreground/5 rounded"
      style={{ fontSize: '13px', color: 'var(--Labels-Tertiary)' }}
    >
      <IconComponent className="h-3.5 w-3.5 flex-shrink-0" style={{ opacity: 0.7 }} />
      <span className="font-medium flex-shrink-0 whitespace-nowrap" style={{ color: 'var(--Labels-Secondary)' }}>
        {displayName}
      </span>
      {summary && (
        <span className="truncate min-w-0" style={{ opacity: 0.6 }}>
          — {summary}
        </span>
      )}
    </button>
  );
}

function EditToolRow({ item, onOpenFile }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const displayName = getDisplayName(item.toolName || 'Edit', t);
  const IconComponent = getToolIcon(item.toolName || 'Edit');

  const args = item.toolCall?.args || {};
  const filePath = getFilePathFromArgs(args);
  const fileName = filePath ? filePath.split('/').pop() : '';
  const oldStr = args.old_string || args.oldString || '';
  const newStr = args.new_string || args.newString || '';
  const hasDiff = !!(oldStr || newStr);

  return (
    <div>
      <div
        className="flex items-center gap-2 px-3 py-1 w-full text-left rounded"
        style={{ fontSize: '13px', color: 'var(--Labels-Tertiary)' }}
      >
        <IconComponent className="h-3.5 w-3.5 flex-shrink-0" style={{ opacity: 0.7 }} />
        <span className="font-medium" style={{ color: 'var(--Labels-Secondary)' }}>
          {displayName}
        </span>
        {fileName && (
          <button
            onClick={() => filePath && onOpenFile?.(filePath)}
            className="truncate transition-colors hover:underline"
            style={{ opacity: 0.6, color: 'var(--color-accent-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 'inherit' }}
          >
            — {fileName}
          </button>
        )}
        {hasDiff && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="ml-auto flex-shrink-0"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'inherit' }}
          >
            <motion.div
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={SPRING}
            >
              <ChevronDown className="h-3 w-3" style={{ opacity: 0.5 }} />
            </motion.div>
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {expanded && hasDiff && (
          <motion.div
            key="diff-content"
            initial={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
            animate={{ height: 'auto', opacity: 1, '--mask-stop': '100%', overflow: 'visible' }}
            exit={{ height: 0, opacity: 0, '--mask-stop': '0%', overflow: 'hidden' }}
            transition={SPRING}
            style={{
              maskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
              WebkitMaskImage: 'linear-gradient(black var(--mask-stop), transparent var(--mask-stop))',
            }}
          >
            <div className="ml-6 mr-2 mt-1 mb-1 rounded overflow-hidden" style={{ fontSize: '12px', border: '1px solid var(--color-border-muted)' }}>
              {oldStr && (
                <div style={{ backgroundColor: 'var(--color-loss-soft)' }}>
                  {oldStr.split('\n').map((line, i) => (
                    <div key={`old-${i}`} className="flex" style={{ minHeight: '20px' }}>
                      <span
                        className="flex-shrink-0 select-none text-right px-2"
                        style={{ color: 'var(--color-loss-muted)', width: '20px', userSelect: 'none' }}
                      >−</span>
                      <pre className="flex-1 font-mono whitespace-pre-wrap break-all m-0 pr-2" style={{ color: 'var(--color-loss)' }}>
                        {line}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
              {newStr && (
                <div style={{ backgroundColor: 'var(--color-profit-soft)' }}>
                  {newStr.split('\n').map((line, i) => (
                    <div key={`new-${i}`} className="flex" style={{ minHeight: '20px' }}>
                      <span
                        className="flex-shrink-0 select-none text-right px-2"
                        style={{ color: 'var(--color-profit-muted)', width: '20px', userSelect: 'none' }}
                      >+</span>
                      <pre className="flex-1 font-mono whitespace-pre-wrap break-all m-0 pr-2" style={{ color: 'var(--color-profit)' }}>
                        {line}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default ActivityBlock;
