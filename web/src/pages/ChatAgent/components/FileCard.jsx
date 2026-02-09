import { FileText, FileCode, Image, Table, ExternalLink, Folder } from 'lucide-react';
import './FileCard.css';

const EXT_ICONS = {
  py: FileCode, js: FileCode, jsx: FileCode, ts: FileCode, tsx: FileCode,
  html: FileCode, css: FileCode, sh: FileCode, bash: FileCode, sql: FileCode,
  csv: Table, json: Table, yaml: Table, yml: Table, xml: Table, toml: Table,
  png: Image, jpg: Image, jpeg: Image, svg: Image, gif: Image, webp: Image,
};

const KNOWN_EXTS = new Set([
  'md', 'txt', 'pdf', 'doc', 'docx', 'rtf',
  'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'css', 'sh', 'bash', 'sql', 'r', 'ipynb',
  'csv', 'json', 'yaml', 'yml', 'xml', 'toml', 'ini', 'cfg', 'log', 'env',
  'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp',
  'zip', 'tar', 'gz',
]);

/**
 * Extract file paths from message text.
 * Matches patterns like dir/file.ext, dir/subdir/file.ext, /home/daytona/results/file.ext.
 * Requires at least one `/` and a known file extension to avoid false positives.
 */
export function extractFilePaths(text) {
  if (!text) return [];
  // Match paths: must have at least one /, end with .extension
  // Handles relative (dir/file.ext) and absolute (/home/daytona/file.ext) paths
  // Handles paths in backticks, quotes, or bare
  const regex = /(?:^|[\s`"'(\[])(\/[a-zA-Z_][^\s`"')\]<>]*\/[^\s`"')\]<>]*\.[a-zA-Z0-9]{1,10}|[a-zA-Z_][^\s`"')\]<>]*\/[^\s`"')\]<>]*\.[a-zA-Z0-9]{1,10})(?=[\s`"')\],:;!?|]|$)/gm;
  const paths = new Set();
  let match;
  while ((match = regex.exec(text)) !== null) {
    let path = match[1];
    // Trim trailing punctuation
    path = path.replace(/[,:;!?]+$/, '');
    const ext = path.split('.').pop().toLowerCase();
    if (!KNOWN_EXTS.has(ext)) continue;
    // Skip URLs
    if (path.startsWith('http') || path.startsWith('www.') || path.startsWith('//')) continue;
    // Normalize absolute sandbox paths to relative
    path = path.replace(/^\/home\/daytona\//, '');
    paths.add(path);
  }
  return Array.from(paths);
}

function FileCard({ path, onOpen }) {
  const ext = path.split('.').pop().toLowerCase();
  const fileName = path.split('/').pop();
  const dirPath = path.split('/').slice(0, -1).join('/');
  const Icon = EXT_ICONS[ext] || FileText;

  return (
    <button className="file-mention-card" onClick={onOpen} title={`Open ${path}`}>
      <Icon className="file-mention-card-icon" />
      <div className="file-mention-card-info">
        <span className="file-mention-card-name">{fileName}</span>
        {dirPath && <span className="file-mention-card-dir">{dirPath}/</span>}
      </div>
      <ExternalLink className="file-mention-card-action" />
    </button>
  );
}

function DirCard({ dir, fileCount, onOpen }) {
  return (
    <button className="file-mention-card file-mention-card-dir-card" onClick={onOpen} title={`Open ${dir}/ in file panel`}>
      <Folder className="file-mention-card-icon" />
      <div className="file-mention-card-info">
        <span className="file-mention-card-name">{dir}/</span>
        <span className="file-mention-card-dir">{fileCount} file{fileCount !== 1 ? 's' : ''}</span>
      </div>
      <ExternalLink className="file-mention-card-action" />
    </button>
  );
}

/**
 * Renders file mention cards below a message.
 * If <= 5 files: show individual file cards.
 * If > 5 files: group by top-level directory, show dir cards + root file cards.
 */
export function FileMentionCards({ filePaths, onOpenFile, onOpenDir }) {
  if (!filePaths || filePaths.length === 0) return null;

  if (filePaths.length <= 5) {
    return (
      <div className="file-mention-cards">
        {filePaths.map((path) => (
          <FileCard key={path} path={path} onOpen={() => onOpenFile(path)} />
        ))}
      </div>
    );
  }

  // Group by top-level directory
  const groups = {};
  const rootFiles = [];
  for (const path of filePaths) {
    const parts = path.split('/');
    if (parts.length > 1) {
      const dir = parts[0];
      if (!groups[dir]) groups[dir] = [];
      groups[dir].push(path);
    } else {
      rootFiles.push(path);
    }
  }

  // Sort directories: results → data → rest alphabetical
  const dirPriority = { results: 0, data: 1 };
  const sortedDirs = Object.entries(groups).sort(([a], [b]) => {
    const pa = dirPriority[a] ?? 2;
    const pb = dirPriority[b] ?? 2;
    if (pa !== pb) return pa - pb;
    return a.localeCompare(b);
  });

  return (
    <div className="file-mention-cards">
      {rootFiles.map((path) => (
        <FileCard key={path} path={path} onOpen={() => onOpenFile(path)} />
      ))}
      {sortedDirs.map(([dir, files]) => (
        <DirCard
          key={dir}
          dir={dir}
          fileCount={files.length}
          onOpen={() => onOpenDir ? onOpenDir(dir) : onOpenFile(files[0])}
        />
      ))}
    </div>
  );
}

export default FileCard;
