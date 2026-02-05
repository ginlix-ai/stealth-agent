import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import ThreadCard from './ThreadCard';
import { getWorkspaceThreads, getWorkspaces } from '../utils/api';
import { DEFAULT_USER_ID } from '../utils/api';

/**
 * ThreadGallery Component
 * 
 * Displays a gallery of threads for a specific workspace.
 * Features:
 * - Lists all threads for the workspace
 * - Shows workspace name in header
 * - Back button to return to workspace gallery
 * - Empty state when no threads exist
 * 
 * @param {string} workspaceId - The workspace ID to show threads for
 * @param {Function} onBack - Callback to navigate back to workspace gallery
 * @param {Function} onThreadSelect - Callback when a thread is selected (receives workspaceId and threadId)
 */
function ThreadGallery({ workspaceId, onBack, onThreadSelect }) {
  const [threads, setThreads] = useState([]);
  const [workspaceName, setWorkspaceName] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const loadingRef = useRef(false);

  // Load workspace name and threads on mount
  useEffect(() => {
    if (!workspaceId) return;
    
    // Guard: Prevent duplicate calls
    if (loadingRef.current) {
      return;
    }
    
    loadingRef.current = true;
    loadData().finally(() => {
      loadingRef.current = false;
    });
  }, [workspaceId]);

  /**
   * Fetches workspace name and threads from the API
   */
  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Load workspace name and threads in parallel
      const [workspacesData, threadsData] = await Promise.all([
        getWorkspaces(DEFAULT_USER_ID).catch(() => ({ workspaces: [] })),
        getWorkspaceThreads(workspaceId, DEFAULT_USER_ID),
      ]);
      
      // Find workspace name
      const workspace = workspacesData.workspaces?.find(
        (ws) => ws.workspace_id === workspaceId
      );
      setWorkspaceName(workspace?.name || 'Workspace');
      
      // Set threads
      setThreads(threadsData.threads || []);
    } catch (err) {
      console.error('Error loading threads:', err);
      setError('Failed to load threads. Please refresh the page.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handles thread selection
   * @param {Object} thread - The selected thread
   */
  const handleThreadClick = (thread) => {
    if (onThreadSelect) {
      onThreadSelect(workspaceId, thread.thread_id);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: '#6155F5' }} />
          <p className="text-sm" style={{ color: '#FFFFFF', opacity: 0.65 }}>
            Loading threads...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4 max-w-md text-center px-4">
          <p className="text-sm" style={{ color: '#FF383C' }}>
            {error}
          </p>
          <button
            onClick={loadData}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              backgroundColor: '#6155F5',
              color: '#FFFFFF',
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: '#1B1D25' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-4 flex-shrink-0"
        style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}
      >
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-md transition-colors hover:bg-white/10"
            style={{ color: '#FFFFFF' }}
            title="Back to workspaces"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-semibold" style={{ color: '#FFFFFF' }}>
            {workspaceName}
          </h1>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {threads.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center h-full py-12">
            <p className="text-base font-medium mb-2" style={{ color: '#FFFFFF' }}>
              No threads yet
            </p>
            <p className="text-sm mb-6 text-center max-w-md" style={{ color: '#FFFFFF', opacity: 0.65 }}>
              Start a conversation to create your first thread
            </p>
          </div>
        ) : (
          // Thread grid
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {threads.map((thread) => (
              <ThreadCard
                key={thread.thread_id}
                thread={thread}
                onClick={() => handleThreadClick(thread)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ThreadGallery;
