import { useState, useEffect } from 'react';
import { useWorkspaceId } from '../contexts/WorkspaceContext';
import { downloadWorkspaceFile } from '../utils/api';

// Module-level cache: workspaceId:path → blobUrl
const blobCache = new Map();

function isExternalUrl(src) {
  return /^(https?:\/\/|data:|blob:)/i.test(src);
}

function normalizeSandboxPath(src) {
  return src.replace(/^\/home\/daytona\//, '');
}

function WorkspaceImage({ src, alt, ...props }) {
  const workspaceId = useWorkspaceId();
  const shouldFetch = !!(workspaceId && src && !isExternalUrl(src));
  const normalizedPath = shouldFetch ? normalizeSandboxPath(src) : '';
  const cacheKey = shouldFetch ? `${workspaceId}:${normalizedPath}` : '';

  const [state, setState] = useState(() =>
    cacheKey && blobCache.has(cacheKey) ? 'loaded' : 'idle'
  );
  const [blobUrl, setBlobUrl] = useState(() =>
    cacheKey ? blobCache.get(cacheKey) || null : null
  );

  useEffect(() => {
    if (!shouldFetch) return;

    const cached = blobCache.get(cacheKey);
    if (cached) {
      setBlobUrl(cached);
      setState('loaded');
      return;
    }

    let cancelled = false;
    setState('loading');

    downloadWorkspaceFile(workspaceId, normalizedPath)
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
  }, [shouldFetch, cacheKey, workspaceId, normalizedPath]);

  // Pass through: no context, no src, or external URL
  if (!shouldFetch) {
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
      <div
        className="rounded-lg my-2 animate-pulse"
        style={{
          width: '100%',
          maxWidth: 480,
          height: 200,
          backgroundColor: 'rgba(255, 255, 255, 0.06)',
        }}
      />
    );
  }

  if (state === 'error') {
    const filename = normalizedPath.split('/').pop();
    return (
      <span className="text-xs my-2 inline-block" style={{ color: 'rgba(255, 255, 255, 0.4)' }}>
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
