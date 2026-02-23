/**
 * Public API functions for shared thread access.
 * All requests are unauthenticated — no Bearer token needed.
 */

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Fetch metadata for a shared thread.
 * @param {string} shareToken
 * @returns {Promise<Object>} { thread_id, title, msg_type, created_at, updated_at, workspace_name, permissions }
 */
export async function getSharedThread(shareToken) {
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}`);
  if (!res.ok) throw new Error(`Shared thread not found (${res.status})`);
  return res.json();
}

/**
 * Replay a shared thread's conversation as SSE events.
 * @param {string} shareToken
 * @param {Function} onEvent - Callback for each parsed SSE event
 */
export async function replaySharedThread(shareToken, onEvent = () => {}) {
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}/replay`);
  if (!res.ok) throw new Error(`Failed to replay shared thread (${res.status})`);

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
        if (ev.id != null) d._eventId = parseInt(ev.id, 10) || ev.id;
        onEvent(d);
      } catch (e) {
        console.warn('[shared-api] SSE parse error', e, line);
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

/**
 * List files in a shared thread's workspace.
 * @param {string} shareToken
 * @param {string} path - Directory path (default ".")
 * @returns {Promise<Object>} { path, files: string[], source }
 */
export async function getSharedFiles(shareToken, path = '.') {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}/files?${params}`);
  if (!res.ok) {
    if (res.status === 403) throw new Error('File access not permitted');
    throw new Error(`Failed to list shared files (${res.status})`);
  }
  return res.json();
}

/**
 * Read a text file from a shared thread's workspace.
 * @param {string} shareToken
 * @param {string} path - File path
 * @returns {Promise<Object>} { path, content, mime, offset, limit, truncated }
 */
export async function readSharedFile(shareToken, path) {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}/files/read?${params}`);
  if (!res.ok) {
    if (res.status === 403) throw new Error('File access not permitted');
    throw new Error(`Failed to read shared file (${res.status})`);
  }
  return res.json();
}

/**
 * Download a raw file from a shared thread's workspace (browser download).
 * @param {string} shareToken
 * @param {string} path - File path
 */
export async function downloadSharedFile(shareToken, path) {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}/files/download?${params}`);
  if (!res.ok) {
    if (res.status === 403) throw new Error('File download not permitted');
    throw new Error(`Failed to download shared file (${res.status})`);
  }
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const fileName = path.split('/').pop() || 'download';
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
}

/**
 * Download a shared file in different modes (needed for FilePanel's rich viewers).
 * @param {string} shareToken
 * @param {string} path - File path
 * @param {'download' | 'blob' | 'arraybuffer'} mode
 * @returns {Promise<void | string | ArrayBuffer>} blob URL, ArrayBuffer, or triggers download
 */
export async function downloadSharedFileAs(shareToken, path, mode = 'download') {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${baseURL}/api/v1/public/shared/${shareToken}/files/download?${params}`);
  if (!res.ok) {
    if (res.status === 403) throw new Error('File download not permitted');
    throw new Error(`Failed to download shared file (${res.status})`);
  }

  if (mode === 'blob') {
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  }
  if (mode === 'arraybuffer') {
    return await res.arrayBuffer();
  }
  // mode === 'download' — trigger browser save
  const blob = await res.blob();
  const fileName = path.split('/').pop() || 'download';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}
