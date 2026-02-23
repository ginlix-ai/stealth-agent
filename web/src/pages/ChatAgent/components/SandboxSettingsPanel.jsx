import React, { useState, useEffect, useMemo } from 'react';
import {
  X, Cpu, MemoryStick, HardDrive, MonitorCog, Play, Square,
  Package, Search, RefreshCw, ChevronDown, ChevronRight,
  Server, Loader2, BookOpen, Archive,
} from 'lucide-react';
import { getSandboxStats, installSandboxPackages, refreshWorkspace } from '../utils/api';
import { api } from '@/api/client';

/**
 * SandboxSettingsPanel — full-screen overlay showing sandbox details.
 *
 * Tabs: Overview | Storage | Packages | Tools & Skills
 */
export default function SandboxSettingsPanel({ onClose, workspaceId }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Package install state
  const [installInput, setInstallInput] = useState('');
  const [installing, setInstalling] = useState(false);
  const [installResult, setInstallResult] = useState(null);

  // Package search
  const [pkgSearch, setPkgSearch] = useState('');

  // Storage expand
  const [showDirBreakdown, setShowDirBreakdown] = useState(false);

  // Tools refresh
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);

  // Start/stop
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    loadStats();
  }, [workspaceId]);

  async function loadStats() {
    setLoading(true);
    setError(null);
    try {
      const data = await getSandboxStats(workspaceId);
      setStats(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load sandbox stats');
    } finally {
      setLoading(false);
    }
  }

  async function handleStartStop(action) {
    setActionLoading(true);
    try {
      await api.post(`/api/v1/workspaces/${workspaceId}/${action}`);
      await loadStats();
    } catch (err) {
      setError(err?.response?.data?.detail || `Failed to ${action} workspace`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleInstall() {
    const packages = installInput.split(/[\s,]+/).filter(Boolean);
    if (!packages.length) return;
    setInstalling(true);
    setInstallResult(null);
    try {
      const result = await installSandboxPackages(workspaceId, packages);
      setInstallResult(result);
      if (result.success) {
        setInstallInput('');
        // Refresh stats to show new packages
        loadStats();
      }
    } catch (err) {
      setInstallResult({
        success: false,
        output: '',
        error: err?.response?.data?.detail || err.message,
        installed: [],
      });
    } finally {
      setInstalling(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshResult(null);
    try {
      const result = await refreshWorkspace(workspaceId);
      setRefreshResult(result);
      // Reload stats to get updated MCP list
      loadStats();
    } catch (err) {
      setRefreshResult({ status: 'error', message: err?.response?.data?.detail || err.message });
    } finally {
      setRefreshing(false);
    }
  }

  // Filter packages by search
  const filteredPackages = useMemo(() => {
    if (!stats?.packages) return [];
    if (!pkgSearch.trim()) return stats.packages;
    const q = pkgSearch.toLowerCase();
    return stats.packages.filter(p => p.name.toLowerCase().includes(q));
  }, [stats?.packages, pkgSearch]);

  const defaultPkgSet = useMemo(
    () => new Set((stats?.default_packages || []).map(p => p.split(/[<>=!~]/)[0].toLowerCase())),
    [stats?.default_packages],
  );

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'storage', label: 'Storage' },
    { key: 'packages', label: 'Packages' },
    { key: 'tools', label: 'Tools & Skills' },
  ];

  const isRunning = stats?.state === 'started';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-bg-overlay-strong)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl rounded-lg p-6"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border-muted)',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-full transition-colors hover:bg-foreground/10"
          style={{ color: 'var(--color-text-primary)' }}
        >
          <X className="h-5 w-5" />
        </button>

        {/* Title */}
        <h2 className="text-xl font-semibold mb-6" style={{ color: 'var(--color-text-primary)' }}>
          Sandbox Settings
        </h2>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b" style={{ borderColor: 'var(--color-border-muted)' }}>
          {tabs.map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className="px-4 py-2 text-sm font-medium"
              style={{
                color: activeTab === t.key ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                borderBottom: activeTab === t.key ? '2px solid var(--color-accent-primary)' : '2px solid transparent',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <LoadingSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={loadStats} />
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewTab
                stats={stats}
                isRunning={isRunning}
                actionLoading={actionLoading}
                onStartStop={handleStartStop}
              />
            )}
            {activeTab === 'storage' && (
              isRunning ? (
                <StorageTab
                  stats={stats}
                  showDirBreakdown={showDirBreakdown}
                  onToggleBreakdown={() => setShowDirBreakdown(!showDirBreakdown)}
                />
              ) : (
                <OfflineTabPlaceholder tabName="storage" />
              )
            )}
            {activeTab === 'packages' && (
              isRunning ? (
                <PackagesTab
                  filteredPackages={filteredPackages}
                  defaultPkgSet={defaultPkgSet}
                  pkgSearch={pkgSearch}
                  onSearchChange={setPkgSearch}
                  installInput={installInput}
                  onInstallInputChange={setInstallInput}
                  installing={installing}
                  installResult={installResult}
                  onInstall={handleInstall}
                />
              ) : (
                <OfflineTabPlaceholder tabName="packages" />
              )
            )}
            {activeTab === 'tools' && (
              isRunning ? (
                <ToolsTab
                  stats={stats}
                  refreshing={refreshing}
                  refreshResult={refreshResult}
                  onRefresh={handleRefresh}
                />
              ) : (
                <OfflineTabPlaceholder tabName="tools & skills" />
              )
            )}
          </>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      {[1, 2, 3, 4].map(i => (
        <div
          key={i}
          className="h-16 rounded-lg animate-pulse"
          style={{ backgroundColor: 'var(--color-border-muted)' }}
        />
      ))}
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center gap-4 py-8">
      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{message}</p>
      <button
        onClick={onRetry}
        className="px-4 py-2 text-sm rounded-md transition-colors hover:bg-foreground/10"
        style={{ color: 'var(--color-accent-primary)', border: '1px solid var(--color-accent-primary)' }}
      >
        Retry
      </button>
    </div>
  );
}


function OfflineTabPlaceholder({ tabName }) {
  return (
    <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
      Start the workspace to view {tabName}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

const TRANSITIONAL_STATES = new Set(['archiving', 'stopping', 'starting']);

function OverviewTab({ stats, isRunning, actionLoading, onStartStop }) {
  const isTransitioning = actionLoading || TRANSITIONAL_STATES.has(stats?.state);
  const resourceCards = [
    { icon: Cpu, label: 'CPU', value: stats.resources.cpu != null ? `${stats.resources.cpu} vCPU` : '—' },
    { icon: MemoryStick, label: 'Memory', value: stats.resources.memory != null ? `${stats.resources.memory} GiB` : '—' },
    { icon: HardDrive, label: 'Disk', value: stats.resources.disk != null ? `${stats.resources.disk} GiB` : '—' },
    { icon: MonitorCog, label: 'GPU', value: stats.resources.gpu != null ? `${stats.resources.gpu} GPU` : '—' },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Resource cards — 2x2 grid */}
      <div className="grid grid-cols-2 gap-3">
        {resourceCards.map(({ icon: Icon, label, value }) => (
          <div
            key={label}
            className="flex items-center gap-3 p-3 rounded-lg"
            style={{ backgroundColor: 'var(--color-border-muted)', border: '1px solid var(--color-border-muted)' }}
          >
            <Icon className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
            <div>
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</div>
              <div className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Status + metadata */}
      <div
        className="flex items-center justify-between p-3 rounded-lg"
        style={{ backgroundColor: 'var(--color-border-muted)', border: '1px solid var(--color-border-muted)' }}
      >
        <div className="flex items-center gap-3">
          {isTransitioning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
          ) : (
            <div
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: isRunning ? 'var(--color-profit)' : 'var(--color-loss)' }}
            />
          )}
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
              {isTransitioning
                ? (actionLoading ? 'Updating...' : stats.state.charAt(0).toUpperCase() + stats.state.slice(1) + '...')
                : isRunning ? 'Running' : stats.state ? stats.state.charAt(0).toUpperCase() + stats.state.slice(1) : 'Unknown'}
            </div>
            {stats.created_at && (
              <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>
                Created {new Date(stats.created_at).toLocaleDateString()}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {stats.auto_stop_interval != null && (
            <span className="text-xs px-2 py-1 rounded" style={{ color: 'var(--color-text-tertiary)', backgroundColor: 'var(--color-border-muted)' }}>
              Auto-stop: {stats.auto_stop_interval}m
            </span>
          )}
          {!isRunning && stats.state === 'stopped' && (
            <button
              onClick={() => onStartStop('archive')}
              disabled={isTransitioning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors hover:bg-foreground/10 disabled:opacity-50"
              style={{ color: 'var(--color-text-tertiary)', border: '1px solid var(--color-border-muted)' }}
            >
              <Archive className="h-3 w-3" />
              Archive
            </button>
          )}
          {isRunning ? (
            <button
              onClick={() => onStartStop('stop')}
              disabled={isTransitioning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors hover:bg-foreground/10 disabled:opacity-50"
              style={{ color: 'var(--color-loss)', border: '1px solid var(--color-border-loss)' }}
            >
              <Square className="h-3 w-3" />
              Stop
            </button>
          ) : (
            <button
              onClick={() => onStartStop('start')}
              disabled={isTransitioning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors hover:bg-foreground/10 disabled:opacity-50"
              style={{ color: 'var(--color-profit)', border: '1px solid var(--color-profit-border)' }}
            >
              <Play className="h-3 w-3" />
              Start
            </button>
          )}
        </div>
      </div>

      {/* Sandbox ID */}
      {stats.sandbox_id && (
        <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          Sandbox ID: <span className="font-mono">{stats.sandbox_id}</span>
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Storage Tab
// ---------------------------------------------------------------------------

function StorageTab({ stats, showDirBreakdown, onToggleBreakdown }) {
  const disk = stats.disk_usage;

  if (!disk) {
    return (
      <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
        Disk usage information unavailable
      </div>
    );
  }

  // Parse use_percent for the progress bar
  const pct = parseInt(disk.use_percent, 10) || 0;

  return (
    <div className="flex flex-col gap-5">
      {/* Usage bar */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-sm" style={{ color: 'var(--color-text-primary)' }}>
          <span>{disk.used} used</span>
          <span>{disk.available} available</span>
        </div>
        <div className="h-3 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--color-border-muted)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${pct}%`,
              backgroundColor: pct > 80 ? 'var(--color-loss)' : 'var(--color-accent-primary)',
            }}
          />
        </div>
        <div className="flex justify-between text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          <span>{disk.use_percent} used</span>
          <span>{disk.total} total</span>
        </div>
      </div>

      {/* Directory breakdown toggle */}
      {stats.directory_breakdown?.length > 0 && (
        <div>
          <button
            onClick={onToggleBreakdown}
            className="flex items-center gap-1.5 text-sm transition-colors hover:opacity-80"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {showDirBreakdown ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            Details ({stats.directory_breakdown.length} directories)
          </button>

          {showDirBreakdown && (
            <div className="mt-3 flex flex-col gap-1">
              {stats.directory_breakdown.map((d) => (
                <div
                  key={d.path}
                  className="flex justify-between py-1.5 px-3 rounded text-sm"
                  style={{ backgroundColor: 'var(--color-border-muted)' }}
                >
                  <span className="font-mono truncate" style={{ color: 'var(--color-text-primary)' }}>{d.path}/</span>
                  <span className="flex-shrink-0 ml-4" style={{ color: 'var(--color-text-tertiary)' }}>{d.size}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Packages Tab
// ---------------------------------------------------------------------------

function PackagesTab({
  filteredPackages, defaultPkgSet, pkgSearch, onSearchChange,
  installInput, onInstallInputChange, installing, installResult, onInstall,
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--color-text-tertiary)' }} />
        <input
          type="text"
          value={pkgSearch}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Filter packages..."
          className="w-full pl-9 pr-3 py-2 text-sm rounded-md bg-transparent outline-none"
          style={{
            color: 'var(--color-text-primary)',
            border: '1px solid var(--color-border-muted)',
          }}
        />
      </div>

      {/* Package list */}
      <div
        className="flex flex-col gap-0.5 overflow-y-auto"
        style={{ maxHeight: '320px' }}
      >
        {filteredPackages.length === 0 ? (
          <div className="py-6 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            {pkgSearch ? 'No matching packages' : 'No packages installed'}
          </div>
        ) : (
          filteredPackages.map(p => {
            const isDefault = defaultPkgSet.has(p.name.toLowerCase());
            return (
              <div
                key={p.name}
                className="flex justify-between items-center py-1.5 px-3 rounded text-sm"
                style={{ backgroundColor: 'var(--color-border-muted)' }}
              >
                <div className="flex items-center gap-2">
                  <span style={{ color: isDefault ? 'var(--color-text-tertiary)' : 'var(--color-text-primary)' }}>
                    {p.name}
                  </span>
                  {isDefault && (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{ color: 'var(--color-text-tertiary)', backgroundColor: 'var(--color-border-muted)' }}
                    >
                      default
                    </span>
                  )}
                </div>
                <span className="font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {p.version}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* Install section */}
      <div
        className="flex flex-col gap-2 pt-3 border-t"
        style={{ borderColor: 'var(--color-border-muted)' }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={installInput}
            onChange={e => onInstallInputChange(e.target.value)}
            placeholder="Package names (e.g. torch transformers>=4.0)"
            onKeyDown={e => e.key === 'Enter' && !installing && onInstall()}
            className="flex-1 px-3 py-2 text-sm rounded-md bg-transparent outline-none"
            style={{
              color: 'var(--color-text-primary)',
              border: '1px solid var(--color-border-muted)',
            }}
          />
          <button
            onClick={onInstall}
            disabled={installing || !installInput.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-md transition-colors disabled:opacity-50"
            style={{
              color: 'var(--color-text-on-accent)',
              backgroundColor: 'var(--color-accent-primary)',
            }}
          >
            {installing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Package className="h-3.5 w-3.5" />}
            Install
          </button>
        </div>

        {/* Install result */}
        {installResult && (
          <div
            className="text-xs p-2 rounded font-mono whitespace-pre-wrap max-h-32 overflow-y-auto"
            style={{
              backgroundColor: 'var(--color-border-muted)',
              color: installResult.success ? 'var(--color-text-secondary)' : 'var(--color-loss)',
            }}
          >
            {installResult.error || installResult.output || 'Done'}
          </div>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Tools & Skills Tab
// ---------------------------------------------------------------------------

function ToolsTab({ stats, refreshing, refreshResult, onRefresh }) {
  return (
    <div className="flex flex-col gap-5">
      {/* MCP Servers list */}
      <div>
        <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-primary)' }}>
          Connected MCP Servers
        </h3>
        {stats.mcp_servers?.length > 0 ? (
          <div className="flex flex-col gap-1">
            {stats.mcp_servers.map(name => (
              <div
                key={name}
                className="flex items-center gap-2.5 py-2 px-3 rounded text-sm"
                style={{ backgroundColor: 'var(--color-border-muted)' }}
              >
                <Server className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
                <span style={{ color: 'var(--color-text-primary)' }}>{name}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-4 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            No MCP servers connected
          </div>
        )}
      </div>

      {/* Skills list */}
      <div>
        <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-primary)' }}>
          Available Skills
        </h3>
        {stats.skills?.length > 0 ? (
          <div className="flex flex-col gap-1">
            {stats.skills.map(skill => (
              <div
                key={skill.name}
                className="flex items-start gap-2.5 py-2 px-3 rounded text-sm"
                style={{ backgroundColor: 'var(--color-border-muted)' }}
              >
                <BookOpen className="h-4 w-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--color-accent-primary)' }} />
                <div className="min-w-0">
                  <span style={{ color: 'var(--color-text-primary)' }}>{skill.name}</span>
                  {skill.description && (
                    <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--color-text-tertiary)' }}>
                      {skill.description}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-4 text-center text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            No skills installed
          </div>
        )}
      </div>

      {/* Sync button */}
      <div
        className="flex flex-col gap-3 pt-3 border-t"
        style={{ borderColor: 'var(--color-border-muted)' }}
      >
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 text-sm rounded-md transition-colors disabled:opacity-50"
          style={{
            color: 'var(--color-text-primary)',
            border: '1px solid var(--color-border-muted)',
            backgroundColor: 'var(--color-border-muted)',
          }}
        >
          {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Sync Tools & Skills
        </button>

        {refreshResult && (
          <div
            className="text-xs p-3 rounded"
            style={{
              backgroundColor: 'var(--color-border-muted)',
              color: refreshResult.status === 'error' ? 'var(--color-loss)' : 'var(--color-text-secondary)',
            }}
          >
            {refreshResult.status === 'error' ? (
              refreshResult.message
            ) : (
              <div className="flex flex-col gap-1">
                <span>Tools refreshed: {refreshResult.refreshed_tools ? 'Yes' : 'No'}</span>
                <span>Skills uploaded: {refreshResult.skills_uploaded ? 'Yes' : 'No'}</span>
                {refreshResult.servers?.length > 0 && (
                  <span>Servers: {refreshResult.servers.length} connected</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
