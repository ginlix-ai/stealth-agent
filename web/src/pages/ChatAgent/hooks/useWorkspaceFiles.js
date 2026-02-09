import { useState, useEffect, useCallback, useRef } from 'react';
import { listWorkspaceFiles } from '../utils/api';

/**
 * Shared hook for workspace file listing.
 * Fetches on mount and when workspaceId changes.
 * Provides a debounced refresh to avoid rapid re-fetches.
 *
 * @param {string} workspaceId
 * @returns {{ files: string[], loading: boolean, error: string|null, refresh: () => void }}
 */
export function useWorkspaceFiles(workspaceId) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const debounceTimerRef = useRef(null);

  const fetchFiles = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listWorkspaceFiles(workspaceId, '.');
      setFiles(data.files || []);
    } catch (err) {
      console.error('[useWorkspaceFiles] Failed to list files:', err);
      setError(
        err?.response?.status === 503
          ? 'Sandbox not available'
          : 'Failed to load files'
      );
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  // Fetch on mount / workspaceId change
  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  // Debounced refresh (500ms) to avoid rapid re-fetches
  const refresh = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      fetchFiles();
      debounceTimerRef.current = null;
    }, 500);
  }, [fetchFiles]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return { files, loading, error, refresh };
}
