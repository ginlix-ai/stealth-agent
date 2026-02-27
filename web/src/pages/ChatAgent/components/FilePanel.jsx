import React, { useState, useEffect, useCallback, useRef, useMemo, Suspense } from 'react';
import { ArrowLeft, X, FileText, FileImage, File, RefreshCw, Download, Upload, Folder, ChevronRight, ChevronDown, ArrowUpDown, AlertTriangle, Trash2, CheckSquare, Square, HardDrive, Printer, Minus, Plus, Pencil, Save, FileDiff, Undo2, Redo2, TextSelect, FolderOpen } from 'lucide-react';
import { useReactToPrint } from 'react-to-print';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTranslation } from 'react-i18next';
import { readWorkspaceFile, readWorkspaceFileFull, writeWorkspaceFile, downloadWorkspaceFile, downloadWorkspaceFileAsArrayBuffer, triggerFileDownload, uploadWorkspaceFile, deleteWorkspaceFiles, backupWorkspaceFiles, getBackupStatus } from '../utils/api';
import { stripLineNumbers } from './toolDisplayConfig';
import Markdown from './Markdown';
import DocumentErrorBoundary from './viewers/DocumentErrorBoundary';
import './FilePanel.css';

const PdfViewer = React.lazy(() => import('./viewers/PdfViewer'));
const ExcelViewer = React.lazy(() => import('./viewers/ExcelViewer'));
const CsvViewer = React.lazy(() => import('./viewers/CsvViewer'));
const HtmlViewer = React.lazy(() => import('./viewers/HtmlViewer'));
const CodeEditor = React.lazy(() => import('./viewers/CodeEditor'));

const EXT_TO_LANG = {
  py: 'python', js: 'javascript', jsx: 'jsx', ts: 'typescript', tsx: 'tsx',
  json: 'json', html: 'html', css: 'css', sql: 'sql', sh: 'bash', bash: 'bash',
  yaml: 'yaml', yml: 'yaml', xml: 'xml', java: 'java', go: 'go', rs: 'rust', rb: 'ruby',
};

const EDITABLE_EXTENSIONS = new Set([
  ...Object.keys(EXT_TO_LANG),
  'md', 'txt', 'csv', 'env', 'toml', 'cfg', 'ini', 'log',
]);

function getFileIcon(fileName) {
  const ext = fileName.split('.').pop()?.toLowerCase();
  if (['md', 'txt', 'csv', 'json', 'py', 'js', 'html'].includes(ext)) return FileText;
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) return FileImage;
  return File;
}

function getFileExtension(fileName) {
  return fileName.split('.').pop()?.toLowerCase() || '';
}

// Map extensions to human-readable type categories
const EXT_TO_TYPE = {
  md: 'Docs', txt: 'Docs', pdf: 'Docs',
  py: 'Code', js: 'Code', jsx: 'Code', ts: 'Code', tsx: 'Code',
  html: 'Code', css: 'Code', sql: 'Code', sh: 'Code', bash: 'Code',
  java: 'Code', go: 'Code', rs: 'Code', rb: 'Code',
  json: 'Data', csv: 'Data', yaml: 'Data', yml: 'Data', xml: 'Data',
  xlsx: 'Data', xls: 'Data',
  png: 'Image', jpg: 'Image', jpeg: 'Image', gif: 'Image', svg: 'Image', webp: 'Image',
};

function getFileType(filePath) {
  const ext = getFileExtension(filePath.split('/').pop() || '');
  return EXT_TO_TYPE[ext] || 'Other';
}

/** Derive available type categories from current file list */
function getAvailableTypes(filePaths) {
  const types = new Set();
  for (const fp of filePaths) types.add(getFileType(fp));
  // Fixed display order, filtered to only those present
  return ['Docs', 'Code', 'Data', 'Image', 'Other'].filter((t) => types.has(t));
}

const PRINT_FONTS = [
  // Sans-serif
  { value: 'system-ui, -apple-system, sans-serif', label: 'System Sans', group: 'Sans-serif' },
  { value: '"Inter", sans-serif', label: 'Inter', group: 'Sans-serif', google: 'Inter' },
  { value: '"Open Sans", sans-serif', label: 'Open Sans', group: 'Sans-serif', google: 'Open+Sans' },
  { value: '"Noto Sans", sans-serif', label: 'Noto Sans', group: 'Sans-serif', google: 'Noto+Sans' },
  { value: '"Roboto", sans-serif', label: 'Roboto', group: 'Sans-serif', google: 'Roboto' },
  // Serif
  { value: '"Merriweather", serif', label: 'Merriweather', group: 'Serif', google: 'Merriweather' },
  { value: '"Lora", serif', label: 'Lora', group: 'Serif', google: 'Lora' },
  { value: '"Source Serif 4", serif', label: 'Source Serif', group: 'Serif', google: 'Source+Serif+4' },
  { value: '"Noto Serif", serif', label: 'Noto Serif', group: 'Serif', google: 'Noto+Serif' },
  // Monospace
  { value: '"JetBrains Mono", monospace', label: 'JetBrains Mono', group: 'Mono', google: 'JetBrains+Mono' },
  { value: '"Fira Code", monospace', label: 'Fira Code', group: 'Mono', google: 'Fira+Code' },
  { value: '"Source Code Pro", monospace', label: 'Source Code Pro', group: 'Mono', google: 'Source+Code+Pro' },
];

const GOOGLE_FONTS_URL = 'https://fonts.googleapis.com/css2?' +
  PRINT_FONTS.filter((f) => f.google)
    .map((f) => `family=${f.google}:wght@400;600;700`)
    .join('&') + '&display=swap';

const PRINT_PRESETS = [
  { label: 'Equity Research', font: '"Inter", sans-serif', size: 11, height: 1.4 },
  { label: 'Academic',        font: '"Source Serif 4", serif', size: 12, height: 1.6 },
  { label: 'Technical',       font: '"JetBrains Mono", monospace', size: 12, height: 1.5 },
  { label: 'General',         font: 'system-ui, -apple-system, sans-serif', size: 14, height: 1.6 },
];

const SORT_OPTIONS = [
  { value: 'name-asc', label: 'Name A-Z' },
  { value: 'name-desc', label: 'Name Z-A' },
  { value: 'type', label: 'Type' },
];

function sortFiles(filePaths, sortBy) {
  const sorted = [...filePaths];
  switch (sortBy) {
    case 'name-asc':
      return sorted.sort((a, b) => {
        const na = a.split('/').pop().toLowerCase();
        const nb = b.split('/').pop().toLowerCase();
        return na.localeCompare(nb);
      });
    case 'name-desc':
      return sorted.sort((a, b) => {
        const na = a.split('/').pop().toLowerCase();
        const nb = b.split('/').pop().toLowerCase();
        return nb.localeCompare(na);
      });
    case 'type':
      return sorted.sort((a, b) => {
        const ea = getFileExtension(a.split('/').pop() || '');
        const eb = getFileExtension(b.split('/').pop() || '');
        if (ea !== eb) return ea.localeCompare(eb);
        return a.split('/').pop().toLowerCase().localeCompare(b.split('/').pop().toLowerCase());
      });
    default:
      return sorted;
  }
}

/** Directory display priority: root first, then results/, data/, rest alphabetical */
const DIR_PRIORITY = { '/': 0, 'results': 1, 'data': 2 };

/** System directory prefixes — collapsed by default when visible */
const SYSTEM_DIR_PREFIXES = ['code', 'tools', 'mcp_servers', 'skills', '.agent'];

function dirSortKey(dir) {
  if (DIR_PRIORITY[dir] != null) return DIR_PRIORITY[dir];
  if (SYSTEM_DIR_PREFIXES.includes(dir)) return 99;
  return 3;
}

/**
 * Builds a recursive file tree from flat file paths.
 * Returns array of top-level TreeNodes sorted by directory priority.
 *
 * TreeNode = { name, fullPath, children: TreeNode[], files: string[] }
 * - name: directory segment name (e.g. "nvidia_dcf_excel")
 * - fullPath: full directory path (e.g. "work/nvidia_dcf_excel")
 * - children: sorted subdirectory nodes
 * - files: leaf file paths (full paths, e.g. "work/nvidia_dcf_excel/create.py")
 */
function buildFileTree(filePaths) {
  // Intermediate map: fullDirPath -> { files, subdirs }
  const dirMap = new Map(); // fullPath -> { files: string[], subdirs: Map<name, fullPath> }

  const getOrCreateDir = (fullPath) => {
    if (!dirMap.has(fullPath)) {
      dirMap.set(fullPath, { files: [], subdirs: new Map() });
    }
    return dirMap.get(fullPath);
  };

  // Root is a special case with fullPath = '/'
  getOrCreateDir('/');

  for (const fp of filePaths) {
    const slashIdx = fp.lastIndexOf('/');
    if (slashIdx < 0) {
      // Root-level file
      getOrCreateDir('/').files.push(fp);
    } else {
      const dirPath = fp.slice(0, slashIdx);
      getOrCreateDir(dirPath).files.push(fp);

      // Ensure all ancestor directories exist and link parent → child
      const segments = dirPath.split('/');
      for (let i = 0; i < segments.length; i++) {
        const parentPath = i === 0 ? '/' : segments.slice(0, i).join('/');
        const childPath = segments.slice(0, i + 1).join('/');
        const childName = segments[i];
        const parent = getOrCreateDir(parentPath);
        if (!parent.subdirs.has(childName)) {
          parent.subdirs.set(childName, childPath);
        }
        getOrCreateDir(childPath);
      }
    }
  }

  // Convert dirMap into recursive TreeNode[] starting from a given path
  const buildNodes = (fullPath) => {
    const entry = dirMap.get(fullPath);
    if (!entry) return { children: [], files: [] };

    const children = Array.from(entry.subdirs.entries())
      .sort(([a], [b]) => {
        const pa = dirSortKey(a);
        const pb = dirSortKey(b);
        if (pa !== pb) return pa - pb;
        return a.localeCompare(b);
      })
      .map(([name, childFullPath]) => {
        const sub = buildNodes(childFullPath);
        return {
          name,
          fullPath: childFullPath,
          children: sub.children,
          files: sub.files,
        };
      });

    return { children, files: entry.files };
  };

  const root = buildNodes('/');

  // Return top-level: root files become a { name: '/', ... } node, plus top-level dirs
  const result = [];
  if (root.files.length > 0) {
    result.push({ name: '/', fullPath: '/', children: [], files: root.files });
  }
  result.push(...root.children);
  return result;
}

/** Count all files recursively under a tree node */
function countTreeFiles(node) {
  let count = node.files.length;
  for (const child of node.children) {
    count += countTreeFiles(child);
  }
  return count;
}

/** Collect all file paths recursively under a tree node */
function collectTreeFiles(node) {
  const result = [...node.files];
  for (const child of node.children) {
    result.push(...collectTreeFiles(child));
  }
  return result;
}

/** Renders vertical indent guide lines for a given depth */
function IndentGuides({ depth }) {
  if (depth <= 0) return null;
  const guides = [];
  for (let i = 0; i < depth; i++) {
    guides.push(
      <span
        key={i}
        className="file-tree-indent-guide"
        style={{ left: i * 16 + 20 }}
      />
    );
  }
  return guides;
}

/** Recursive directory node renderer for the file tree */
function DirectoryNode({
  node, depth, showHeader,
  collapsedDirs, toggleDir,
  selectMode, selectedPaths, toggleSelect, toggleDirSelect,
  handleFileClick, readOnly, backedUpSet, modifiedSet,
  onAddContext, setContextMenu,
}) {
  const isRoot = node.name === '/';
  const isCollapsed = collapsedDirs.has(node.fullPath);
  const allFiles = collectTreeFiles(node);
  const totalCount = allFiles.length;
  const indent = (depth + 1) * 16 + 8; // base 8px + 16px per depth level

  return (
    <div key={node.fullPath}>
      {showHeader && (
        <div
          className="file-panel-dir-header file-tree-row"
          style={depth > 0 ? { paddingLeft: depth * 16 + 8 } : undefined}
          onClick={() => selectMode ? toggleDirSelect(allFiles) : toggleDir(node.fullPath)}
        >
          <IndentGuides depth={depth} />
          {selectMode ? (
            allFiles.every((f) => selectedPaths.has(f))
              ? <CheckSquare className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
              : <Square className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
          ) : isCollapsed
            ? <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
            : <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
          }
          <Folder className="h-3.5 w-3.5 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
          <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text-tertiary)' }}>
            {isRoot ? '/' : `${node.name}/`}
          </span>
          <span className="text-xs" style={{ color: 'var(--color-icon-muted)' }}>
            {totalCount}
          </span>
        </div>
      )}
      {(!isCollapsed || selectMode) && (
        <>
          {/* Subdirectories */}
          {node.children.map((child) => (
            <DirectoryNode
              key={child.fullPath}
              node={child}
              depth={showHeader ? depth + 1 : depth}
              showHeader={true}
              collapsedDirs={collapsedDirs}
              toggleDir={toggleDir}
              selectMode={selectMode}
              selectedPaths={selectedPaths}
              toggleSelect={toggleSelect}
              toggleDirSelect={toggleDirSelect}
              handleFileClick={handleFileClick}
              readOnly={readOnly}
              backedUpSet={backedUpSet}
              modifiedSet={modifiedSet}
              onAddContext={onAddContext}
              setContextMenu={setContextMenu}
            />
          ))}
          {/* Files in this directory */}
          {node.files.map((filePath) => {
            const name = filePath.split('/').pop();
            const Icon = getFileIcon(name);
            const isSelected = selectedPaths.has(filePath);
            const fileDepth = showHeader ? depth + 1 : depth;
            return (
              <div
                key={filePath}
                className={`file-panel-item file-tree-row ${selectMode && isSelected ? 'file-panel-item-selected' : ''}`}
                style={{ paddingLeft: showHeader ? indent : undefined }}
                onClick={() => selectMode ? toggleSelect(filePath) : handleFileClick(filePath)}
                onContextMenu={!selectMode && onAddContext ? (e) => {
                  e.preventDefault();
                  setContextMenu({ x: e.clientX, y: e.clientY, filePath });
                } : undefined}
              >
                <IndentGuides depth={fileDepth} />
                {selectMode ? (
                  isSelected
                    ? <CheckSquare className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
                    : <Square className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
                ) : (
                  <Icon className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
                )}
                <span className="text-sm truncate" style={{ color: 'var(--color-text-primary)' }}>{name}</span>
                {!readOnly && !selectMode && (backedUpSet.has(filePath) || modifiedSet.has(filePath)) && (
                  <span
                    className={`file-panel-backup-dot ${backedUpSet.has(filePath) ? 'backed-up' : 'modified'}`}
                    title={backedUpSet.has(filePath) ? 'Backed up' : 'Modified since last backup'}
                  />
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

function DocumentLoadingFallback() {
  return (
    <div className="flex items-center justify-center py-12">
      <RefreshCw className="h-5 w-5 animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
    </div>
  );
}

function DocumentErrorFallback({ onDownload }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <AlertTriangle className="h-6 w-6" style={{ color: 'var(--color-text-tertiary)' }} />
      <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>Unable to preview this file</p>
      <button
        className="text-xs px-3 py-1.5 rounded"
        style={{ background: 'var(--color-accent-soft)', color: 'var(--color-accent-primary)', border: '1px solid var(--color-accent-overlay)' }}
        onClick={onDownload}
      >
        Download instead
      </button>
    </div>
  );
}

function FilePanel({
  workspaceId,
  onClose,
  targetFile,
  onTargetFileHandled,
  targetDirectory,
  onTargetDirHandled,
  // Shared file list from useWorkspaceFiles hook
  files = [],
  filesLoading = false,
  filesError = null,
  onRefreshFiles,
  readOnly = false,
  apiAdapter = null,
  onAddContext = null,
  showSystemFiles = false,
  onToggleSystemFiles = null,
}) {
  const { t } = useTranslation();
  // Resolve API functions — use adapter overrides if provided, otherwise fall back to authenticated imports
  const readFileFn = apiAdapter?.readFile
    ? (_, path) => apiAdapter.readFile(path)
    : readWorkspaceFile;
  const downloadFileFn = apiAdapter?.downloadFile
    ? (_, path) => apiAdapter.downloadFile(path)
    : downloadWorkspaceFile;
  const downloadFileAsArrayBufferFn = apiAdapter?.downloadFileAsArrayBuffer
    ? (_, path) => apiAdapter.downloadFileAsArrayBuffer(path)
    : downloadWorkspaceFileAsArrayBuffer;
  const triggerDownloadFn = apiAdapter?.triggerDownload
    ? (_, path) => apiAdapter.triggerDownload(path)
    : triggerFileDownload;
  const writeFileFn = apiAdapter?.writeFile
    ? (_, path, content) => apiAdapter.writeFile(path, content)
    : writeWorkspaceFile;
  const readFileFullFn = apiAdapter?.readFileFull
    ? (_, path) => apiAdapter.readFileFull(path)
    : readWorkspaceFileFull;

  // File detail view state
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState(null);
  const [fileArrayBuffer, setFileArrayBuffer] = useState(null);
  const [fileMime, setFileMime] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);

  // Upload state
  const [uploadProgress, setUploadProgress] = useState(null); // null = idle, 0-100 = uploading
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);
  const markdownRef = useRef(null);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [showDiff, setShowDiff] = useState(false);
  const [originalContent, setOriginalContent] = useState(null);
  const editorRef = useRef(null);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const handleUndoRedoChange = useCallback(({ canUndo: u, canRedo: r }) => {
    setCanUndo(u);
    setCanRedo(r);
  }, []);

  // Selection tooltip state ("Add to context")
  const [selectionTooltip, setSelectionTooltip] = useState(null); // { x, y, text, lineStart?, lineEnd? }
  const contentWrapperRef = useRef(null);

  // Right-click context menu state
  const [contextMenu, setContextMenu] = useState(null); // { x, y, filePath }

  // Close context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [contextMenu]);

  // Clear selection tooltip when navigating away from a file
  useEffect(() => {
    setSelectionTooltip(null);
  }, [selectedFile]);

  // Clear selection tooltip on mousedown if selection is empty
  useEffect(() => {
    if (!selectionTooltip) return;
    const handler = () => {
      setTimeout(() => {
        const sel = window.getSelection();
        if (!sel || !sel.toString().trim()) setSelectionTooltip(null);
      }, 10);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [selectionTooltip]);

  // Handle text selection in read-only views (Markdown, SyntaxHighlighter, etc.)
  const handleContentMouseUp = useCallback(() => {
    if (!onAddContext || !selectedFile) return;
    // Small delay to let the browser finalize the selection
    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || !sel.toString().trim()) {
        setSelectionTooltip(null);
        return;
      }
      const text = sel.toString();
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const wrapper = contentWrapperRef.current;
      const wrapperRect = wrapper?.getBoundingClientRect();
      if (!wrapperRect) return;

      // Account for scroll position — the tooltip is position:absolute inside a scrollable container
      const scrollTop = wrapper.scrollTop || 0;
      const scrollLeft = wrapper.scrollLeft || 0;

      // Determine accurate SOURCE line numbers (matching what the agent sees)
      let lineStart, lineEnd;

      const startNode = range.startContainer.nodeType === 3
        ? range.startContainer.parentElement
        : range.startContainer;
      const endNode = range.endContainer.nodeType === 3
        ? range.endContainer.parentElement
        : range.endContainer;

      // Method 1: data-line attributes from SyntaxHighlighter (wrapLines + lineProps)
      // These give exact source line numbers for code views
      const startLineEl = startNode?.closest?.('[data-line]');
      const endLineEl = endNode?.closest?.('[data-line]');
      if (startLineEl && endLineEl) {
        lineStart = parseInt(startLineEl.dataset.line, 10);
        lineEnd = parseInt(endLineEl.dataset.line, 10);
      }

      // Method 2: Source-text matching — search for selected text in raw fileContent
      // This is critical for markdown views where DOM text differs from source
      if (lineStart == null && fileContent && typeof fileContent === 'string') {
        const selectedLines = text.split('\n').filter((l) => l.trim());
        const firstLine = (selectedLines[0] || '').trim();
        const lastLine = selectedLines.length > 1 ? (selectedLines[selectedLines.length - 1] || '').trim() : firstLine;

        // Extract significant words (3+ chars) for fuzzy matching in source
        const getSearchWords = (line) => line.split(/\s+/).filter((w) => w.replace(/[^a-zA-Z0-9]/g, '').length > 2);

        const findLineInSource = (searchLine, fromLine = 0) => {
          const words = getSearchWords(searchLine);
          if (words.length < 2) {
            // For short selections, try direct substring match
            const fragment = searchLine.substring(0, Math.min(searchLine.length, 40));
            if (fragment.length >= 5) {
              const sourceLines = fileContent.split('\n');
              for (let i = fromLine; i < sourceLines.length; i++) {
                if (sourceLines[i].includes(fragment)) return i + 1;
              }
            }
            return null;
          }
          // Build regex: allow markdown syntax characters between words
          try {
            const pattern = words.slice(0, 8).map((w) =>
              w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
            ).join('[\\s\\S]{0,30}');
            const regex = new RegExp(pattern);
            const sourceLines = fileContent.split('\n');
            for (let i = fromLine; i < sourceLines.length; i++) {
              if (regex.test(sourceLines[i])) return i + 1;
            }
          } catch { /* regex failed — fall through */ }
          return null;
        };

        lineStart = findLineInSource(firstLine);
        if (lineStart != null) {
          if (firstLine !== lastLine) {
            lineEnd = findLineInSource(lastLine, lineStart - 1);
          }
          if (lineEnd == null) lineEnd = lineStart + (text.match(/\n/g) || []).length;
        }
      }

      // Method 3: DOM range counting fallback (for non-markdown views if data-line missed)
      if (lineStart == null) {
        try {
          const contentRoot = startNode?.closest?.('pre') || startNode?.closest?.('.p-4');
          if (contentRoot && !startNode?.closest?.('.markdown-print-content')) {
            const preRange = document.createRange();
            preRange.selectNodeContents(contentRoot);
            preRange.setEnd(range.startContainer, range.startOffset);
            const fragment = preRange.cloneContents();
            fragment.querySelectorAll('[style*="user-select"]').forEach((el) => el.remove());
            const textBefore = fragment.textContent;
            lineStart = (textBefore.match(/\n/g) || []).length + 1;
            lineEnd = lineStart + (text.match(/\n/g) || []).length;
          }
        } catch {
          // Range operations can throw in edge cases — fall through
        }
      }

      setSelectionTooltip({
        x: rect.left - wrapperRect.left + scrollLeft + rect.width / 2,
        y: rect.top - wrapperRect.top + scrollTop - 8,
        text,
        lineStart,
        lineEnd,
      });
    }, 10);
  }, [onAddContext, selectedFile, fileContent]);

  // Handle text selection from Monaco editor (CodeEditor)
  const handleEditorTextSelect = useCallback((selData) => {
    if (!onAddContext || !selectedFile) return;
    if (!selData) {
      setSelectionTooltip(null);
      return;
    }
    // Position tooltip near the selection using rect from Monaco
    const wrapper = contentWrapperRef.current;
    const wrapperRect = wrapper?.getBoundingClientRect();
    let x = 120, y = 8;
    if (selData.rect && wrapperRect) {
      x = selData.rect.left - wrapperRect.left + 50;
      y = selData.rect.top - wrapperRect.top - 8;
    }
    setSelectionTooltip({
      x, y,
      text: selData.text,
      lineStart: selData.startLine,
      lineEnd: selData.endLine,
    });
  }, [onAddContext, selectedFile]);

  const handleAddSelectionContext = useCallback(() => {
    if (!selectionTooltip || !selectedFile || !onAddContext) return;
    const { text, lineStart, lineEnd } = selectionTooltip;
    const fileName = selectedFile.split('/').pop();
    const lineCount = lineStart != null && lineEnd != null ? lineEnd - lineStart + 1 : (text.match(/\n/g) || []).length + 1;
    const label = lineStart != null
      ? (lineStart === lineEnd ? `${fileName}:L${lineStart}` : `${fileName}:L${lineStart}-${lineEnd}`)
      : fileName;
    onAddContext({ path: selectedFile, snippet: text, label, lineStart, lineEnd, lineCount });
    setSelectionTooltip(null);
    window.getSelection()?.removeAllRanges();
  }, [selectionTooltip, selectedFile, onAddContext]);

  const handleContextMenuAction = useCallback((action, filePath) => {
    setContextMenu(null);
    if (action === 'add-context' && onAddContext) {
      onAddContext({ path: filePath });
    } else if (action === 'open') {
      handleFileClick(filePath);
    }
  }, [onAddContext]); // eslint-disable-line react-hooks/exhaustive-deps

  // Print / PDF export state
  const [printMode, setPrintMode] = useState(false);
  const [printFontSize, setPrintFontSize] = useState(11);
  const [printLineHeight, setPrintLineHeight] = useState(1.4);
  const [printFontFamily, setPrintFontFamily] = useState(PRINT_FONTS[1].value);

  const activePreset = useMemo(
    () => PRINT_PRESETS.find((p) => p.font === printFontFamily && p.size === printFontSize && p.height === printLineHeight),
    [printFontFamily, printFontSize, printLineHeight],
  );
  const activePresetLabel = activePreset?.label ?? '';

  const handlePrint = useReactToPrint({ contentRef: markdownRef });

  const exitPrintMode = useCallback(() => {
    setPrintMode(false);
  }, []);

  // Lazy-load Google Fonts when print mode activates
  useEffect(() => {
    if (!printMode) return;
    const id = 'print-google-fonts';
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = GOOGLE_FONTS_URL;
    document.head.appendChild(link);
  }, [printMode]);

  // Filter and sort state
  const [filterType, setFilterType] = useState('All'); // 'All' | 'Docs' | 'Code' | 'Data' | 'Image' | 'Other'
  const [sortBy, setSortBy] = useState('name-asc');
  const [showSortMenu, setShowSortMenu] = useState(false);
  const sortMenuRef = useRef(null);

  // Selection / delete state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedPaths, setSelectedPaths] = useState(new Set());
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Backup (file persistence) state
  // backedUpSet: files unchanged since last backup
  // modifiedSet: files changed since last backup
  // untracked files = everything else (not in either set)
  const [backedUpSet, setBackedUpSet] = useState(new Set());
  const [modifiedSet, setModifiedSet] = useState(new Set());
  const [backingUp, setBackingUp] = useState(false);
  const [backupResult, setBackupResult] = useState(null);

  const updateBackupStatus = useCallback((data) => {
    setBackedUpSet(new Set(data.backed_up || []));
    setModifiedSet(new Set(data.modified || []));
  }, []);

  // Fetch backup status on mount and when files change (skip in readOnly mode)
  useEffect(() => {
    if (!workspaceId || readOnly) return;
    getBackupStatus(workspaceId)
      .then(updateBackupStatus)
      .catch(() => {});
  }, [workspaceId, files, updateBackupStatus, readOnly]);

  const handleBackup = useCallback(async () => {
    if (!workspaceId || backingUp) return;
    setBackingUp(true);
    setBackupResult(null);
    try {
      const result = await backupWorkspaceFiles(workspaceId);
      setBackupResult(result);
      // Refresh backup status
      const status = await getBackupStatus(workspaceId);
      updateBackupStatus(status);
      setTimeout(() => setBackupResult(null), 3000);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Backup failed';
      setBackupResult({ error: msg });
      setTimeout(() => setBackupResult(null), 4000);
    } finally {
      setBackingUp(false);
    }
  }, [workspaceId, backingUp, updateBackupStatus]);

  const availableTypes = useMemo(() => getAvailableTypes(files), [files]);

  // Apply directory filter, type filter, sort, then group
  const filteredSortedFiles = useMemo(() => {
    let result = files;
    // Filter by target directory when navigating from a directory card
    if (targetDirectory) {
      const prefix = targetDirectory.endsWith('/') ? targetDirectory : targetDirectory + '/';
      result = result.filter((fp) => fp.startsWith(prefix));
    }
    if (filterType !== 'All') {
      result = result.filter((fp) => getFileType(fp) === filterType);
    }
    return sortFiles(result, sortBy);
  }, [files, filterType, sortBy, targetDirectory]);

  // Directory collapse state
  const [collapsedDirs, setCollapsedDirs] = useState(new Set());
  const fileTree = useMemo(() => buildFileTree(filteredSortedFiles), [filteredSortedFiles]);

  // Auto-collapse system directories when they appear in the tree
  useEffect(() => {
    if (!showSystemFiles) return;
    const sysDirs = fileTree
      .filter((node) => SYSTEM_DIR_PREFIXES.includes(node.name))
      .map((node) => node.fullPath);
    if (sysDirs.length === 0) return;
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const d of sysDirs) {
        if (!next.has(d)) { next.add(d); changed = true; }
      }
      return changed ? next : prev;
    });
  }, [fileTree, showSystemFiles]);

  const toggleDir = useCallback((dir) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir);
      else next.add(dir);
      return next;
    });
  }, []);

  // Selection helpers
  const toggleSelect = useCallback((path) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedPaths((prev) => {
      if (prev.size === filteredSortedFiles.length) return new Set();
      return new Set(filteredSortedFiles);
    });
  }, [filteredSortedFiles]);

  const toggleDirSelect = useCallback((dirFiles) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      const allSelected = dirFiles.every((f) => next.has(f));
      dirFiles.forEach((f) => (allSelected ? next.delete(f) : next.add(f)));
      return next;
    });
  }, []);

  const exitSelectMode = useCallback(() => {
    setSelectMode(false);
    setSelectedPaths(new Set());
    setDeleteError(null);
    setDeleteConfirm(false);
  }, []);

  const handleDelete = useCallback(() => {
    if (selectedPaths.size === 0) return;
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    const paths = Array.from(selectedPaths);
    exitSelectMode();
    setDeleteLoading(true);
    setDeleteError(null);
    deleteWorkspaceFiles(workspaceId, paths)
      .then((result) => {
        if (result.errors?.length > 0) {
          setDeleteError(t('filePanel.deletePartialFail', { count: result.errors.length }));
        }
      })
      .catch((err) => {
        setDeleteError(err?.response?.data?.detail || err?.message || t('filePanel.deleteFailed'));
      })
      .finally(() => {
        setDeleteLoading(false);
        onRefreshFiles?.();
      });
  }, [selectedPaths, workspaceId, deleteConfirm, exitSelectMode, onRefreshFiles]);

  // Auto-dismiss delete confirmation after 4 seconds
  useEffect(() => {
    if (!deleteConfirm) return;
    const timer = setTimeout(() => setDeleteConfirm(false), 4000);
    return () => clearTimeout(timer);
  }, [deleteConfirm]);

  // Reset select mode when directory filter changes
  useEffect(() => { exitSelectMode(); }, [targetDirectory]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close sort menu on outside click
  useEffect(() => {
    if (!showSortMenu) return;
    const handler = (e) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(e.target)) {
        setShowSortMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSortMenu]);

  // Drag-and-drop state
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  // Cleanup blob URL on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      if (fileMime === 'image' && fileContent) {
        URL.revokeObjectURL(fileContent);
      }
    };
  }, [fileContent, fileMime]);

  // Auto-open file when targetFile prop changes (from chat tool call click)
  useEffect(() => {
    if (targetFile) {
      handleFileClick(targetFile);
      onTargetFileHandled?.();
    }
  }, [targetFile]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileClick = async (filePath) => {
    const ext = getFileExtension(filePath);

    // Binary files
    if (['pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'xlsx', 'docx', 'zip'].includes(ext)) {
      // For images, show inline via blob URL
      if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) {
        // Revoke previous blob URL before loading new image
        if (fileMime === 'image' && fileContent) {
          URL.revokeObjectURL(fileContent);
        }
        setSelectedFile(filePath);
        setFileLoading(true);
        setFileMime('image');
        try {
          const blobUrl = await downloadFileFn(workspaceId, filePath);
          setFileContent(blobUrl);
        } catch (err) {
          console.error('[FilePanel] Failed to download image:', err);
          setFileContent(null);
          setFileMime('text/plain');
          setFileContent('Error: Failed to load image');
        } finally {
          setFileLoading(false);
        }
        return;
      }
      // PDF — preview inline
      if (ext === 'pdf') {
        setSelectedFile(filePath);
        setFileLoading(true);
        setFileMime('pdf');
        try {
          const buf = await downloadFileAsArrayBufferFn(workspaceId, filePath);
          setFileArrayBuffer(buf);
        } catch (err) {
          console.error('[FilePanel] Failed to load PDF:', err);
          setFileMime('error');
        } finally {
          setFileLoading(false);
        }
        return;
      }
      // Excel — preview inline
      if (ext === 'xlsx' || ext === 'xls') {
        setSelectedFile(filePath);
        setFileLoading(true);
        setFileMime('excel');
        try {
          const buf = await downloadFileAsArrayBufferFn(workspaceId, filePath);
          setFileArrayBuffer(buf);
        } catch (err) {
          console.error('[FilePanel] Failed to load Excel file:', err);
          setFileMime('error');
        } finally {
          setFileLoading(false);
        }
        return;
      }
      // For other binary files, trigger download
      try {
        await triggerDownloadFn(workspaceId, filePath);
      } catch (err) {
        console.error('[FilePanel] Failed to download file:', err);
      }
      return;
    }

    // Text files - read content
    setSelectedFile(filePath);
    setFileLoading(true);
    try {
      const data = await readFileFn(workspaceId, filePath);
      setFileContent(data.content || '');
      setFileMime(data.mime || 'text/plain');
    } catch (err) {
      console.error('[FilePanel] Failed to read file:', err);
      setFileContent('Error: Failed to load file content');
      setFileMime('text/plain');
    } finally {
      setFileLoading(false);
    }
  };

  // Compute whether current file is editable
  const selectedExt = selectedFile ? getFileExtension(selectedFile.split('/').pop() || '') : '';
  const canEdit = selectedFile
    && !readOnly
    && !printMode
    && EDITABLE_EXTENSIONS.has(selectedExt)
    && fileMime !== 'image'
    && fileMime !== 'error'
    && fileMime !== 'pdf'
    && fileMime !== 'excel'
    && !['html', 'htm'].includes(selectedExt)
    && !selectedFile.startsWith('/large_tool_results/');

  const hasUnsavedChanges = isEditing && editContent !== null && editContent !== fileContent;

  const handleBack = () => {
    if (hasUnsavedChanges) {
      if (!window.confirm(t('filePanel.discardUnsaved'))) return;
    }
    if (fileMime === 'image' && fileContent) {
      URL.revokeObjectURL(fileContent);
    }
    setSelectedFile(null);
    setFileContent(null);
    setFileArrayBuffer(null);
    setFileMime(null);
    setPrintMode(false);
    setIsEditing(false);
    setEditContent(null);
    setShowDiff(false);
    setOriginalContent(null);
    editorRef.current = null;
    setCanUndo(false);
    setCanRedo(false);
    setSaveError(null);
    // Don't clear targetDirectory — stay in directory view after closing file detail
  };

  const handleStartEdit = useCallback(async () => {
    if (!selectedFile || !workspaceId) return;
    setSaveError(null);
    try {
      const data = await readFileFullFn(workspaceId, selectedFile);
      const fullContent = data.content || '';
      // Guard against very large files in browser editor
      if (fullContent.length > 500 * 1024) {
        setSaveError(t('filePanel.fileTooLarge'));
        return;
      }
      setEditContent(fullContent);
      setOriginalContent(fullContent);
      setFileContent(fullContent);
      setIsEditing(true);
    } catch (err) {
      console.error('[FilePanel] Failed to fetch full file for editing:', err);
      setSaveError(err?.response?.data?.detail || err?.message || t('filePanel.loadEditFailed'));
    }
  }, [selectedFile, workspaceId, readFileFullFn]);

  const handleEditorChange = useCallback((value) => {
    setEditContent(value);
  }, []);

  const handleSave = useCallback(async () => {
    if (!selectedFile || !workspaceId || editContent === null) return;
    if (!window.confirm(t('filePanel.confirmSave'))) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await writeFileFn(workspaceId, selectedFile, editContent);
      setFileContent(editContent);
      setIsEditing(false);
      setEditContent(null);
      setShowDiff(false);
      setOriginalContent(null);
    } catch (err) {
      console.error('[FilePanel] Save failed:', err);
      setSaveError(err?.response?.data?.detail || err?.message || t('filePanel.saveFailed'));
    } finally {
      setIsSaving(false);
    }
  }, [selectedFile, workspaceId, editContent, writeFileFn]);

  const handleCancelEdit = useCallback(() => {
    if (hasUnsavedChanges) {
      if (!window.confirm(t('filePanel.discardChanges'))) return;
    }
    setIsEditing(false);
    setEditContent(null);
    setShowDiff(false);
    setOriginalContent(null);
    setSaveError(null);
  }, [hasUnsavedChanges]);

  // Cmd/Ctrl+S keyboard shortcut for save
  useEffect(() => {
    if (!isEditing) return;
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        if (editContent !== null && editContent !== fileContent) {
          handleSave();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isEditing, editContent, fileContent, handleSave]);

  // beforeunload guard for unsaved changes
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);

  // Upload handling
  const handleUpload = useCallback(async (file) => {
    if (!file || !workspaceId) return;
    setUploadError(null);
    setUploadProgress(0);
    try {
      await uploadWorkspaceFile(workspaceId, file, null, (pct) => setUploadProgress(pct));
      setUploadProgress(null);
      onRefreshFiles?.();
    } catch (err) {
      console.error('[FilePanel] Upload failed:', err);
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed';
      setUploadError(msg);
      setUploadProgress(null);
    }
  }, [workspaceId, onRefreshFiles]);

  const handleFileInputChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    // Reset input so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [handleUpload]);

  // Drag-and-drop handlers
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  const fileName = selectedFile?.split('/').pop() || '';

  return (
    <div className="file-panel">
      {/* Header */}
      <div className="file-panel-header">
        <div className="flex items-center gap-2 min-w-0">
          {selectedFile ? (
            <button onClick={handleBack} className="file-panel-icon-btn" title={t('filePanel.backToFileList')}>
              <ArrowLeft className="h-4 w-4" />
            </button>
          ) : targetDirectory ? (
            <button onClick={() => onTargetDirHandled?.()} className="file-panel-icon-btn" title={t('filePanel.backToAllFiles')}>
              <ArrowLeft className="h-4 w-4" />
            </button>
          ) : null}
          <span className="text-sm font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
            {selectedFile ? (<>{fileName}{hasUnsavedChanges && <span style={{ color: 'var(--color-text-tertiary)' }}> *</span>}</>) : targetDirectory ? `${targetDirectory}/` : t('chat.workspaceFiles')}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {!selectedFile && !selectMode && (
            <>
              {!readOnly && files.length > 0 && (
                <button
                  onClick={() => setSelectMode(true)}
                  className="file-panel-icon-btn"
                  title={t('filePanel.selectFiles')}
                >
                  <CheckSquare className="h-4 w-4" />
                </button>
              )}
              {!readOnly && (
                <>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="file-panel-icon-btn"
                    title={t('filePanel.uploadFile')}
                    disabled={uploadProgress !== null}
                  >
                    <Upload className="h-4 w-4" />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={handleFileInputChange}
                  />
                  <button
                    onClick={handleBackup}
                    className="file-panel-icon-btn"
                    title={t('filePanel.backupFiles')}
                    disabled={backingUp}
                  >
                    <HardDrive className={`h-4 w-4 ${backingUp ? 'animate-pulse' : ''}`} />
                  </button>
                </>
              )}
              {!readOnly && (
                <button
                  onClick={onRefreshFiles}
                  className="file-panel-icon-btn"
                  title={t('filePanel.refresh')}
                >
                  <RefreshCw className={`h-4 w-4 ${filesLoading ? 'animate-spin' : ''}`} />
                </button>
              )}
            </>
          )}
          {!readOnly && !selectedFile && selectMode && (
            <>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>
                {selectedPaths.size} selected
              </span>
              <button
                onClick={toggleSelectAll}
                className="file-panel-chip"
                style={{ marginLeft: 2, fontSize: 10, padding: '1px 6px' }}
              >
                {selectedPaths.size === filteredSortedFiles.length ? 'Deselect All' : 'Select All'}
              </button>
              {deleteConfirm ? (
                <button
                  onClick={handleDelete}
                  className="file-panel-delete-confirm-btn"
                  disabled={deleteLoading}
                >
                  Delete {selectedPaths.size}?
                </button>
              ) : (
                <button
                  onClick={handleDelete}
                  className="file-panel-icon-btn"
                  title={t('filePanel.deleteSelected')}
                  disabled={selectedPaths.size === 0 || deleteLoading}
                  style={selectedPaths.size > 0 ? { color: 'var(--color-icon-danger)' } : undefined}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
              <button onClick={exitSelectMode} className="file-panel-icon-btn" title={t('filePanel.cancelSelection')}>
                <X className="h-4 w-4" />
              </button>
            </>
          )}
          {selectedFile && !isEditing && (
            <>
              <button
                onClick={async () => {
                  try {
                    await triggerDownloadFn(workspaceId, selectedFile);
                  } catch (err) {
                    console.error('[FilePanel] Download failed:', err);
                  }
                }}
                className="file-panel-icon-btn"
                title={t('filePanel.download')}
              >
                <Download className="h-4 w-4" />
              </button>
              {canEdit && (
                <button
                  onClick={handleStartEdit}
                  className="file-panel-icon-btn"
                  title={t('filePanel.editFile')}
                >
                  <Pencil className="h-4 w-4" />
                </button>
              )}
              {(getFileExtension(selectedFile) === 'md' || fileMime?.includes('markdown')) && (
                <button
                  onClick={() => setPrintMode((v) => !v)}
                  className={`file-panel-icon-btn ${printMode ? 'file-panel-icon-btn-active' : ''}`}
                  title={printMode ? t('filePanel.closePrintSettings') : t('filePanel.savePdf')}
                >
                  <Printer className="h-4 w-4" />
                </button>
              )}
            </>
          )}
          {selectedFile && isEditing && (
            <>
              {saveError && (
                <span className="text-xs truncate" style={{ color: 'var(--color-icon-danger)', maxWidth: 120 }} title={saveError}>
                  {saveError}
                </span>
              )}
              <button
                onClick={() => editorRef.current?.trigger('toolbar', 'undo')}
                className="file-panel-icon-btn"
                title={t('filePanel.undo')}
                disabled={!canUndo}
              >
                <Undo2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => editorRef.current?.trigger('toolbar', 'redo')}
                className="file-panel-icon-btn"
                title={t('filePanel.redo')}
                disabled={!canRedo}
              >
                <Redo2 className="h-4 w-4" />
              </button>
              {hasUnsavedChanges && (
                <button
                  onClick={() => setShowDiff((d) => !d)}
                  className={`file-panel-icon-btn ${showDiff ? 'file-panel-icon-btn-active' : ''}`}
                  title={showDiff ? t('filePanel.hideDiff') : t('filePanel.showDiff')}
                >
                  <FileDiff className="h-4 w-4" />
                </button>
              )}
              <button
                onClick={handleSave}
                className="file-panel-icon-btn"
                title={t('filePanel.save')}
                disabled={!hasUnsavedChanges || isSaving}
              >
                <Save className={`h-4 w-4 ${isSaving ? 'animate-pulse' : ''}`} />
              </button>
              <button
                onClick={handleCancelEdit}
                className="file-panel-icon-btn"
                title={t('filePanel.cancelEditing')}
              >
                <X className="h-4 w-4" />
              </button>
            </>
          )}
          {!selectMode && !isEditing && (
            <button onClick={onClose} className="file-panel-icon-btn" title={t('filePanel.close')}>
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Upload progress bar */}
      {uploadProgress !== null && (
        <div className="file-panel-upload-progress">
          <div
            className="file-panel-upload-progress-bar"
            style={{ width: `${uploadProgress}%` }}
          />
        </div>
      )}

      {/* Upload error */}
      {uploadError && (
        <div className="file-panel-upload-error">
          <span>{uploadError}</span>
          <button onClick={() => setUploadError(null)} className="file-panel-icon-btn">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Delete progress (indeterminate) */}
      {deleteLoading && (
        <div className="file-panel-progress-indeterminate" />
      )}

      {/* Delete error */}
      {deleteError && (
        <div className="file-panel-upload-error">
          <span>{deleteError}</span>
          <button onClick={() => setDeleteError(null)} className="file-panel-icon-btn">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Backup result notification */}
      {backupResult && (
        <div className={`file-panel-backup-result ${backupResult.error ? 'error' : ''}`}>
          <span>
            {backupResult.error
              ? backupResult.error
              : `Backed up ${backupResult.synced} file${backupResult.synced !== 1 ? 's' : ''}${backupResult.skipped ? `, ${backupResult.skipped} unchanged` : ''}`}
          </span>
          <button onClick={() => setBackupResult(null)} className="file-panel-icon-btn" style={{ padding: 2 }}>
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Backup progress (indeterminate) */}
      {backingUp && (
        <div className="file-panel-progress-indeterminate" />
      )}

      {/* Editing hint banner */}
      {isEditing && (
        <div className="file-panel-edit-hint">
          <Pencil className="h-3 w-3" style={{ flexShrink: 0 }} />
          <span>{t('filePanel.editingHint')}</span>
        </div>
      )}

      {/* Print settings toolbar */}
      {printMode && selectedFile && (
        <div className="print-settings-toolbar">
          <div className="print-settings-row">
            <span className="print-settings-label">Style</span>
            <select
              className="print-settings-select"
              value={activePresetLabel}
              onChange={(e) => {
                const preset = PRINT_PRESETS.find((p) => p.label === e.target.value);
                if (preset) {
                  setPrintFontFamily(preset.font);
                  setPrintFontSize(preset.size);
                  setPrintLineHeight(preset.height);
                }
              }}
            >
              {PRINT_PRESETS.map((p) => (
                <option key={p.label} value={p.label}>{p.label}</option>
              ))}
              {!activePreset && <option value="" disabled>Custom</option>}
            </select>
          </div>
          <div className="print-settings-row">
            <span className="print-settings-label">Font</span>
            <select
              className="print-settings-select"
              value={printFontFamily}
              onChange={(e) => setPrintFontFamily(e.target.value)}
            >
              {['Sans-serif', 'Serif', 'Mono'].map((group) => (
                <optgroup key={group} label={group}>
                  {PRINT_FONTS.filter((f) => f.group === group).map((f) => (
                    <option key={f.label} value={f.value}>{f.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div className="print-settings-row">
            <span className="print-settings-label">Size</span>
            <div className="print-settings-stepper">
              <button
                className="print-settings-stepper-btn"
                onClick={() => setPrintFontSize((v) => Math.max(10, v - 1))}
                disabled={printFontSize <= 10}
              >
                <Minus className="h-3 w-3" />
              </button>
              <span className="print-settings-stepper-value">{printFontSize}px</span>
              <button
                className="print-settings-stepper-btn"
                onClick={() => setPrintFontSize((v) => Math.min(22, v + 1))}
                disabled={printFontSize >= 22}
              >
                <Plus className="h-3 w-3" />
              </button>
            </div>
            <span className="print-settings-label" style={{ marginLeft: 12 }}>Height</span>
            <div className="print-settings-stepper">
              <button
                className="print-settings-stepper-btn"
                onClick={() => setPrintLineHeight((v) => Math.max(1.2, +(v - 0.2).toFixed(1)))}
                disabled={printLineHeight <= 1.2}
              >
                <Minus className="h-3 w-3" />
              </button>
              <span className="print-settings-stepper-value">{printLineHeight.toFixed(1)}</span>
              <button
                className="print-settings-stepper-btn"
                onClick={() => setPrintLineHeight((v) => Math.min(2.4, +(v + 0.2).toFixed(1)))}
                disabled={printLineHeight >= 2.4}
              >
                <Plus className="h-3 w-3" />
              </button>
            </div>
          </div>
          <button
            className="print-settings-print-btn"
            onClick={handlePrint}
          >
            <Printer className="h-3.5 w-3.5" />
            Save as PDF
          </button>
        </div>
      )}

      {/* Filter & Sort toolbar — only in file list view */}
      {!selectedFile && !filesLoading && !filesError && files.length > 0 && (
        <div className="file-panel-toolbar">
          {/* Type filter chips */}
          <div className="file-panel-filter-chips">
            <button
              className={`file-panel-chip ${filterType === 'All' ? 'active' : ''}`}
              onClick={() => setFilterType('All')}
            >
              All
            </button>
            {availableTypes.map((t) => (
              <button
                key={t}
                className={`file-panel-chip ${filterType === t ? 'active' : ''}`}
                onClick={() => setFilterType(filterType === t ? 'All' : t)}
              >
                {t}
              </button>
            ))}
          </div>
          {/* System files toggle */}
          {onToggleSystemFiles && (
            <button
              className={`file-panel-chip ${showSystemFiles ? 'active' : ''}`}
              onClick={onToggleSystemFiles}
              title="Show system directories (.agent/, code/, tools/, etc.)"
            >
              System
            </button>
          )}
          {/* Sort dropdown */}
          <div className="file-panel-sort-wrapper" ref={sortMenuRef}>
            <button
              className="file-panel-icon-btn"
              title={t('filePanel.sortFiles')}
              onClick={() => setShowSortMenu((v) => !v)}
            >
              <ArrowUpDown className="h-3.5 w-3.5" />
            </button>
            {showSortMenu && (
              <div className="file-panel-sort-menu">
                {SORT_OPTIONS.map((opt) => (
                  <div
                    key={opt.value}
                    className={`file-panel-sort-item ${sortBy === opt.value ? 'active' : ''}`}
                    onClick={() => { setSortBy(opt.value); setShowSortMenu(false); }}
                  >
                    {opt.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Content */}
      <div
        className="file-panel-content-wrapper"
        onDragEnter={!readOnly && !selectedFile ? handleDragEnter : undefined}
        onDragLeave={!readOnly && !selectedFile ? handleDragLeave : undefined}
        onDragOver={!readOnly && !selectedFile ? handleDragOver : undefined}
        onDrop={!readOnly && !selectedFile ? handleDrop : undefined}
        style={{ position: 'relative', flex: 1, minHeight: 0, overflow: 'hidden' }}
      >
        {/* Drag overlay */}
        {!readOnly && isDragOver && !selectedFile && (
          <div className="file-panel-drag-overlay">
            <Upload className="h-8 w-8" style={{ color: 'var(--color-accent-primary)' }} />
            <span>Drop file to upload</span>
          </div>
        )}

        <div className="file-panel-content" ref={contentWrapperRef}>
          {/* Selection tooltip */}
          {selectionTooltip && onAddContext && (
            <div
              className="file-panel-selection-tooltip"
              style={{
                left: Math.max(8, selectionTooltip.x - 60),
                top: Math.max(4, selectionTooltip.y - 32),
              }}
              onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); handleAddSelectionContext(); }}
            >
              <TextSelect className="h-3.5 w-3.5" style={{ color: 'var(--color-accent-primary)' }} />
              {selectionTooltip.lineStart != null
                ? (selectionTooltip.lineEnd !== selectionTooltip.lineStart
                    ? t('context.addLinesToContext', { start: selectionTooltip.lineStart, end: selectionTooltip.lineEnd })
                    : t('context.addLineToContext', { line: selectionTooltip.lineStart }))
                : t('context.addToContext')}
            </div>
          )}

          {/* Right-click context menu */}
          {contextMenu && (
            <div
              className="file-panel-context-menu"
              style={{ left: contextMenu.x, top: contextMenu.y }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              {onAddContext && (
                <div
                  className="file-panel-context-menu-item"
                  onClick={() => handleContextMenuAction('add-context', contextMenu.filePath)}
                >
                  <TextSelect className="h-3.5 w-3.5" style={{ color: 'var(--color-text-tertiary)' }} />
                  {t('context.addToContext')}
                </div>
              )}
              <div
                className="file-panel-context-menu-item"
                onClick={() => handleContextMenuAction('open', contextMenu.filePath)}
              >
                <FolderOpen className="h-3.5 w-3.5" style={{ color: 'var(--color-text-tertiary)' }} />
                {t('context.openFile')}
              </div>
            </div>
          )}

          {selectedFile ? (
            // File Detail View
            fileLoading ? (
              <div className="p-4">
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-5 w-5 animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
                </div>
              </div>
            ) : fileMime === 'pdf' ? (
              <Suspense fallback={<DocumentLoadingFallback />}>
                <DocumentErrorBoundary fallback={<DocumentErrorFallback onDownload={() => triggerDownloadFn(workspaceId, selectedFile).catch((err) => console.error('[FilePanel] Download failed:', err))} />}>
                  <PdfViewer data={fileArrayBuffer} />
                </DocumentErrorBoundary>
              </Suspense>
            ) : fileMime === 'excel' ? (
              <Suspense fallback={<DocumentLoadingFallback />}>
                <DocumentErrorBoundary fallback={<DocumentErrorFallback onDownload={() => triggerDownloadFn(workspaceId, selectedFile).catch((err) => console.error('[FilePanel] Download failed:', err))} />}>
                  <ExcelViewer data={fileArrayBuffer} />
                </DocumentErrorBoundary>
              </Suspense>
            ) : getFileExtension(selectedFile) === 'csv' ? (
              isEditing ? (
                <div className="file-panel-editor-container">
                  <Suspense fallback={<DocumentLoadingFallback />}>
                    <CodeEditor value={editContent} onChange={handleEditorChange} fileName={selectedFile} diffMode={showDiff} originalValue={originalContent} editorRef={editorRef} onUndoRedoChange={handleUndoRedoChange} onTextSelect={onAddContext ? handleEditorTextSelect : undefined} />
                  </Suspense>
                </div>
              ) : (
                <Suspense fallback={<DocumentLoadingFallback />}>
                  <DocumentErrorBoundary fallback={<DocumentErrorFallback onDownload={() => triggerDownloadFn(workspaceId, selectedFile).catch((err) => console.error('[FilePanel] Download failed:', err))} />}>
                    <CsvViewer content={fileContent} />
                  </DocumentErrorBoundary>
                </Suspense>
              )
            ) : ['html', 'htm'].includes(getFileExtension(selectedFile)) ? (
              <Suspense fallback={<DocumentLoadingFallback />}>
                <DocumentErrorBoundary fallback={<DocumentErrorFallback onDownload={() => triggerDownloadFn(workspaceId, selectedFile).catch((err) => console.error('[FilePanel] Download failed:', err))} />}>
                  <HtmlViewer content={fileContent} />
                </DocumentErrorBoundary>
              </Suspense>
            ) : isEditing ? (
              <div className="file-panel-editor-container">
                <Suspense fallback={<DocumentLoadingFallback />}>
                  <CodeEditor value={editContent} onChange={handleEditorChange} fileName={selectedFile} diffMode={showDiff} originalValue={originalContent} editorRef={editorRef} onUndoRedoChange={handleUndoRedoChange} onTextSelect={onAddContext ? handleEditorTextSelect : undefined} />
                </Suspense>
              </div>
            ) : (
              <div className="p-4" onMouseUp={handleContentMouseUp}>
                {fileMime === 'image' ? (
                  <img src={fileContent} alt={fileName} className="max-w-full rounded" />
                ) : fileMime === 'error' ? (
                  <DocumentErrorFallback onDownload={() => triggerDownloadFn(workspaceId, selectedFile).catch((err) => console.error('[FilePanel] Download failed:', err))} />
                ) : selectedFile?.startsWith('/large_tool_results/') ? (
                  <div
                    ref={markdownRef}
                    className={`markdown-print-content ${printMode ? 'print-preview-active' : ''}`}
                    style={printMode ? { '--print-font-size': `${printFontSize}px`, '--print-line-height': printLineHeight, '--print-font-family': printFontFamily } : undefined}
                  >
                    <Markdown variant="panel" content={stripLineNumbers(fileContent)} className={printMode ? undefined : 'text-sm'} />
                  </div>
                ) : fileMime?.includes('markdown') || getFileExtension(selectedFile) === 'md' ? (
                  <div
                    ref={markdownRef}
                    className={`markdown-print-content ${printMode ? 'print-preview-active' : ''}`}
                    style={printMode ? { '--print-font-size': `${printFontSize}px`, '--print-line-height': printLineHeight, '--print-font-family': printFontFamily } : undefined}
                  >
                    <Markdown variant="panel" content={fileContent} className={printMode ? undefined : 'text-sm'} />
                  </div>
                ) : (
                  <SyntaxHighlighter
                    language={EXT_TO_LANG[getFileExtension(selectedFile)] || 'text'}
                    style={typeof window !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light' ? oneLight : oneDark}
                    customStyle={{ margin: 0, padding: 0, backgroundColor: 'transparent', fontSize: '12px', lineHeight: '1.6' }}
                    codeTagProps={{ style: { backgroundColor: 'transparent' } }}
                    showLineNumbers
                    lineNumberStyle={{ minWidth: '2.5em', paddingRight: '1em', color: 'var(--color-text-tertiary)', userSelect: 'none', fontSize: '11px', opacity: 0.5 }}
                    wrapLines
                    lineProps={(lineNumber) => ({ 'data-line': lineNumber })}
                    wrapLongLines
                  >
                    {fileContent}
                  </SyntaxHighlighter>
                )}
              </div>
            )
          ) : (
            // File List View
            <div className="py-1 file-tree-root">
              {filesLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="file-panel-item animate-pulse">
                    <div className="h-4 w-4 rounded" style={{ backgroundColor: 'var(--color-border-muted)' }} />
                    <div className="h-4 flex-1 rounded" style={{ backgroundColor: 'var(--color-border-muted)', width: `${50 + i * 10}%` }} />
                  </div>
                ))
              ) : filesError ? (
                <div className="px-4 py-8 text-center">
                  <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>{filesError}</p>
                </div>
              ) : files.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No files yet</p>
                </div>
              ) : filteredSortedFiles.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No {filterType.toLowerCase()} files</p>
                </div>
              ) : (
                fileTree.map((node) => (
                  <DirectoryNode
                    key={node.fullPath}
                    node={node}
                    depth={0}
                    showHeader={node.name !== '/' || fileTree.length > 1}
                    collapsedDirs={collapsedDirs}
                    toggleDir={toggleDir}
                    selectMode={selectMode}
                    selectedPaths={selectedPaths}
                    toggleSelect={toggleSelect}
                    toggleDirSelect={toggleDirSelect}
                    handleFileClick={handleFileClick}
                    readOnly={readOnly}
                    backedUpSet={backedUpSet}
                    modifiedSet={modifiedSet}
                    onAddContext={onAddContext}
                    setContextMenu={setContextMenu}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default FilePanel;
