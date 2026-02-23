import { useState, useEffect } from 'react';
import { useWorkspaceId, useWorkspaceDownloadFile } from '../contexts/WorkspaceContext';
import { downloadWorkspaceFile } from '../utils/api';

// Module-level cache: key:path → blobUrl
const blobCache = new Map();

function isExternalUrl(src) {
  return /^(https?:\/\/|data:|blob:)/i.test(src);
}

function normalizeSandboxPath(src) {
  return src.replace(/^\/home\/daytona\//, '');
}

function WorkspaceImage({ src, alt, ...props }) {
  const workspaceId = useWorkspaceId();
  const downloadFileFn = useWorkspaceDownloadFile();
  const canFetch = !!(src && !isExternalUrl(src) && (workspaceId || downloadFileFn));
  const normalizedPath = canFetch ? normalizeSandboxPath(src) : '';
  const cacheKey = canFetch ? `${workspaceId || 'shared'}:${normalizedPath}` : '';

  const [state, setState] = useState(() =>
    cacheKey && blobCache.has(cacheKey) ? 'loaded' : 'idle'
  );
  const [blobUrl, setBlobUrl] = useState(() =>
    cacheKey ? blobCache.get(cacheKey) || null : null
  );

  useEffect(() => {
    if (!canFetch) return;

    const cached = blobCache.get(cacheKey);
    if (cached) {
      setBlobUrl(cached);
      setState('loaded');
      return;
    }

    let cancelled = false;
    setState('loading');

    const fetcher = downloadFileFn
      ? downloadFileFn(normalizedPath)
      : downloadWorkspaceFile(workspaceId, normalizedPath);

    fetcher
      .then((url) => {
        if (cancelled) return;
        blobCache.set(cacheKey, url);
        setBlobUrl(url);
        setState('loaded');
      })
      .catch(() => {
        if (cancelled) return;
        setState('error');
      });

    return () => { cancelled = true; };
  }, [canFetch, cacheKey, workspaceId, normalizedPath, downloadFileFn]);

  // Pass through: no context, no src, or external URL
  if (!canFetch) {
    return (
      <img
        className="rounded-lg my-2"
        style={{ maxWidth: '100%', height: 'auto' }}
        src={src}
        alt={alt}
        {...props}
      />
    );
  }

  if (state === 'loading' || state === 'idle') {
    return (
      <span
        className="rounded-lg my-2 animate-pulse"
        style={{
          display: 'block',
          width: '100%',
          maxWidth: 480,
          height: 200,
          backgroundColor: 'var(--color-border-muted)',
        }}
      />
    );
  }

  if (state === 'error') {
    const filename = normalizedPath.split('/').pop();
    return (
      <span className="text-xs my-2 inline-block" style={{ color: 'var(--color-text-tertiary)' }}>
        [image: {filename}]
      </span>
    );
  }

  return (
    <img
      className="rounded-lg my-2"
      style={{ maxWidth: '100%', height: 'auto' }}
      src={blobUrl}
      alt={alt}
      {...props}
    />
  );
}

export default WorkspaceImage;
