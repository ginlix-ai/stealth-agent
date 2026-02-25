import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Plus, Loader2, Search, ArrowDownUp, MoreHorizontal, Zap, MessageSquareText } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import CreateWorkspaceModal from './CreateWorkspaceModal';
import DeleteConfirmModal from './DeleteConfirmModal';
import MorphingPageDots from '../../../components/ui/morphing-page-dots';
import { getWorkspaces, createWorkspace, deleteWorkspace, getFlashWorkspace } from '../utils/api';
import { removeStoredThreadId } from '../hooks/useChatMessages';
import { clearChatSession } from '../hooks/utils/chatSessionRestore';
import '../../Dashboard/Dashboard.css';

const PAGE_SIZE = 20;

/**
 * WorkspaceGallery Component
 * 
 * Displays a gallery of workspaces as cards.
 * Features:
 * - Lists all workspaces for the user
 * - "Create Workspace" button that opens a modal
 * - Empty state when no workspaces exist
 * - Handles workspace creation
 * 
 * @param {Function} onWorkspaceSelect - Callback when a workspace is selected (receives workspaceId)
 */
function WorkspaceGallery({ onWorkspaceSelect, cache, prefetchThreads }) {
  const { t } = useTranslation();
  const [workspaces, setWorkspaces] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, workspace: null });
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('activity'); // 'activity' or 'name'
  const [totalWorkspaces, setTotalWorkspaces] = useState(0);
  const [currentPage, setCurrentPage] = useState(0);
  const navigate = useNavigate();
  const { workspaceId: currentWorkspaceId } = useParams();
  const loadingRef = useRef(false);
  const searchTimerRef = useRef(null);
  const isSearching = searchQuery.length > 0;
  const totalPages = Math.ceil(totalWorkspaces / PAGE_SIZE);

  // Clear saved chat session so tab-switching returns to workspace gallery
  useEffect(() => {
    clearChatSession();
  }, []);

  // Load workspaces on mount, using cache for instant display on return navigation
  useEffect(() => {
    // Guard: Prevent duplicate calls
    if (loadingRef.current) {
      return;
    }

    // Show cached data instantly (stale-while-revalidate)
    if (cache?.current?.workspaces) {
      setWorkspaces(cache.current.workspaces);
      if (cache.current.total != null) {
        setTotalWorkspaces(cache.current.total);
      }
      setIsLoading(false);
    }

    loadingRef.current = true;
    loadWorkspaces(0).finally(() => {
      loadingRef.current = false;
    });
  }, []);

  // Re-fetch when page changes (skip initial mount which is handled above)
  const initialMountRef = useRef(true);
  useEffect(() => {
    if (initialMountRef.current) {
      initialMountRef.current = false;
      return;
    }
    if (!isSearching) {
      loadWorkspaces(currentPage);
    }
  }, [currentPage]);

  /**
   * Fetches workspaces from the API with pagination.
   * Filters out '__flash__' workspaces (created by TradingCenter).
   * @param {number} page - 0-indexed page number
   */
  const loadWorkspaces = async (page = currentPage) => {
    try {
      const hasCached = cache?.current?.workspaces;
      if (!hasCached) setIsLoading(true);
      setError(null);
      const data = await getWorkspaces(PAGE_SIZE, page * PAGE_SIZE);
      // Filter out '__flash__' workspaces
      const filteredWorkspaces = (data.workspaces || []).filter(
        (ws) => ws.name !== '__flash__'
      );
      const total = data.total ?? filteredWorkspaces.length;
      setWorkspaces(filteredWorkspaces);
      setTotalWorkspaces(total);

      // Update cache
      if (cache?.current) {
        cache.current.workspaces = filteredWorkspaces;
        cache.current.total = total;
        cache.current.fetchedAt = Date.now();
      }
    } catch (err) {
      console.error('Error loading workspaces:', err);
      setError(t('workspace.failedLoadWorkspaces'));
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Debounced search: fetch all workspaces matching query
   */
  const handleSearchChange = useCallback((value) => {
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);

    if (value.length > 0) {
      searchTimerRef.current = setTimeout(async () => {
        try {
          const data = await getWorkspaces(100, 0);
          const filtered = (data.workspaces || []).filter(
            (ws) => ws.name !== '__flash__'
          );
          setWorkspaces(filtered);
        } catch (err) {
          console.error('Error searching workspaces:', err);
        }
      }, 300);
    } else {
      // Search cleared — return to paginated view
      loadWorkspaces(currentPage);
    }
  }, [currentPage]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  /**
   * Handles workspace creation
   * @param {Object} workspaceData - Object with name and description
   */
  const handleCreateWorkspace = async (workspaceData) => {
    try {
      const newWorkspace = await createWorkspace(
        workspaceData.name,
        workspaceData.description,
      );
      // Add new workspace to the list
      setWorkspaces((prev) => [newWorkspace, ...prev]);
      // Return workspace so modal can use workspace_id for file uploads
      return newWorkspace;
    } catch (err) {
      console.error('Error creating workspace:', err);
      throw err; // Let modal handle the error display
    }
  };

  /**
   * Handles delete icon click - opens confirmation modal
   * @param {Object} workspace - The workspace to delete
   */
  const handleDeleteClick = (workspace) => {
    setDeleteModal({ isOpen: true, workspace });
    setDeleteError(null);
  };

  /**
   * Handles confirmed workspace deletion
   */
  const handleConfirmDelete = async () => {
    if (!deleteModal.workspace) return;

    const workspaceToDelete = deleteModal.workspace;
    const workspaceId = workspaceToDelete.workspace_id;

    if (!workspaceId) {
      console.error('No workspace ID found in workspace object:', workspaceToDelete);
      setDeleteError(t('workspace.invalidWorkspace'));
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteWorkspace(workspaceId);

      // Clean up localStorage: remove thread ID for deleted workspace
      removeStoredThreadId(workspaceId);

      // Remove workspace from list and adjust total
      setWorkspaces((prev) => {
        const updated = prev.filter((ws) => ws.workspace_id !== workspaceId);
        // If page is now empty, go to previous page
        if (updated.length === 0 && currentPage > 0) {
          setCurrentPage((p) => p - 1);
        }
        return updated;
      });
      setTotalWorkspaces((prev) => Math.max(0, prev - 1));

      // If the deleted workspace is currently active, navigate back to gallery
      if (currentWorkspaceId === workspaceId) {
        navigate('/chat');
      }

      // Close modal
      setDeleteModal({ isOpen: false, workspace: null });
    } catch (err) {
      console.error('Error deleting workspace:', err);
      const errorMessage = err.message || t('workspace.failedDeleteWorkspace');
      setDeleteError(errorMessage);
      // Keep modal open so user can see the error
    } finally {
      setIsDeleting(false);
    }
  };

  /**
   * Handles canceling deletion
   */
  const handleCancelDelete = () => {
    setDeleteModal({ isOpen: false, workspace: null });
    setDeleteError(null);
  };

  /**
   * Filter and sort workspaces
   */
  const filteredAndSortedWorkspaces = workspaces
    .filter((workspace) =>
      workspace.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      // Pin flash workspace to top
      const aFlash = a.status === 'flash' ? 1 : 0;
      const bFlash = b.status === 'flash' ? 1 : 0;
      if (aFlash !== bFlash) return bFlash - aFlash;

      if (sortBy === 'activity') {
        // Sort by updated_at (most recent first)
        return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
      } else {
        // Sort by name (alphabetical)
        return a.name.localeCompare(b.name);
      }
    });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: 'var(--color-accent-primary)' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
            {t('workspace.loadingWorkspaces')}
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4 max-w-md text-center px-4">
          <p className="text-sm" style={{ color: 'var(--color-loss)' }}>
            {error}
          </p>
          <button
            onClick={loadWorkspaces}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              backgroundColor: 'var(--color-accent-primary)',
              color: 'var(--color-text-on-accent)',
            }}
          >
            {t('common.retry')}
          </button>
        </div>
      </div>
    );
  }

  const hasWorkspaces = workspaces.length > 0;

  return (
    <div
      className="h-full flex flex-col overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-page)',
        backgroundImage: 'radial-gradient(circle at center, var(--color-dot-grid) 0.75px, transparent 0.75px)',
        backgroundSize: '18px 18px',
        backgroundPosition: '0 0'
      }}
    >
      {/* Header */}
      <header className="flex w-full h-16 md:h-24 md:items-end mx-auto max-w-4xl flex-shrink-0 px-4 md:px-8">
        <div className="flex w-full items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold hidden md:block dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
            {t('workspace.workspaces')}
          </h1>
          <div></div>
          {hasWorkspaces && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 h-9 rounded-lg transition-all hover:scale-[1.01] active:scale-[0.985]"
              style={{
                backgroundColor: 'var(--color-accent-primary)',
                color: 'var(--color-text-on-accent)',
              }}
            >
              <Plus className="h-4 w-4" />
              <span className="text-sm font-medium">{t('workspace.newWorkspace')}</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto mt-4 w-full flex-1 px-4 md:px-8 lg:mt-6 max-w-4xl min-h-0 flex flex-col pb-0">
        <h1 className="text-xl font-semibold mb-4 md:hidden dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
          Workspaces
        </h1>

        <div className="overflow-auto pb-20 px-1">
          {hasWorkspaces && (
          <div className="sticky top-0 z-[5] flex flex-col gap-4 pb-4 md:pb-8">
            {/* Search Bar */}
            <div className="w-full">
              <div
                className="flex items-center gap-2 h-11 px-3 rounded-xl border transition-colors"
                style={{
                  backgroundColor: 'var(--color-bg-input)',
                  borderColor: 'var(--color-border-muted)',
                }}
              >
                <Search className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--color-text-tertiary)' }} />
                <input
                  className="w-full bg-transparent outline-none text-sm"
                  style={{ color: 'var(--color-text-primary)' }}
                  placeholder={t('workspace.searchWorkspaces')}
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                />
              </div>
            </div>

            {/* Sort By */}
            <div className="flex w-full gap-4 justify-between items-center">
              <div></div>
              <div className="flex items-center gap-2.5">
                <span className="text-sm hidden md:inline" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('workspace.sortBy')}
                </span>
                <button
                  onClick={() => setSortBy(sortBy === 'activity' ? 'name' : 'activity')}
                  className="flex items-center gap-1 md:gap-1.5 px-2 md:px-3 py-1 h-9 rounded-lg border transition-colors hover:bg-foreground/5"
                  style={{ borderColor: 'var(--color-border-muted)', color: 'var(--color-text-tertiary)' }}
                >
                  <ArrowDownUp className="h-4 w-4 md:hidden" />
                  <span className="text-sm hidden md:inline">{sortBy === 'activity' ? t('workspace.activity') : t('common.name')}</span>
                  <span className="text-sm md:hidden">{sortBy === 'activity' ? t('workspace.activity') : t('common.name')}</span>
                </button>
              </div>
            </div>
          </div>
          )}

          {/* Projects Grid */}
          {filteredAndSortedWorkspaces.length === 0 ? (
            // Empty state
            <div className="flex flex-col items-center justify-center py-16">
              {searchQuery ? (
                <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                  {t('workspace.noWorkspacesFound')}
                </p>
              ) : (
                <>
                  <p className="text-lg font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    {t('workspace.welcomeTitle')}
                  </p>
                  <p className="text-sm mb-8" style={{ color: 'var(--color-text-tertiary)' }}>
                    {t('workspace.welcomeDesc')}
                  </p>
                  <div className="flex flex-col sm:flex-row items-center gap-3">
                    <button
                      onClick={async () => {
                        try {
                          const flashWs = await getFlashWorkspace();
                          navigate(`/chat/${flashWs.workspace_id}/__default__`, {
                            state: {
                              isOnboarding: true,
                              agentMode: 'flash',
                              workspaceStatus: 'flash',
                            },
                          });
                        } catch (err) {
                          console.error('Error starting onboarding:', err);
                        }
                      }}
                      className="flex items-center gap-2 px-6 py-3 rounded-lg transition-all hover:scale-[1.01] active:scale-[0.985]"
                      style={{
                        backgroundColor: 'var(--color-accent-primary)',
                        color: 'var(--color-text-on-accent)',
                      }}
                    >
                      <MessageSquareText className="h-5 w-5" />
                      <span className="font-medium">{t('settings.startOnboarding')}</span>
                    </button>
                    <button
                      onClick={() => setIsModalOpen(true)}
                      className="flex items-center gap-2 px-6 py-3 rounded-lg border transition-all hover:bg-foreground/5 hover:scale-[1.01] active:scale-[0.985]"
                      style={{
                        borderColor: 'var(--color-border-muted)',
                        color: 'var(--color-text-primary)',
                      }}
                    >
                      <Plus className="h-5 w-5" />
                      <span className="font-medium">{t('workspace.createWorkspace')}</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 md:gap-6 grid-cols-1 auto-rows-fr mb-3 md:mb-6">
              {filteredAndSortedWorkspaces.map((workspace) => (
                <div key={workspace.workspace_id} className="h-full">
                  <div
                    className="relative group h-full"
                    onMouseEnter={() => prefetchThreads?.(workspace.workspace_id)}
                  >
                    <div
                      onClick={() => onWorkspaceSelect(workspace.workspace_id, workspace.name, workspace.status)}
                      className="relative flex cursor-pointer flex-col overflow-hidden rounded-xl py-4 pl-5 pr-4 transition-all ease-in-out hover:shadow-sm active:scale-[0.98] h-full w-full"
                      style={{
                        background: workspace.status === 'flash'
                          ? 'linear-gradient(to bottom, var(--color-accent-soft), var(--color-bg-subtle))'
                          : 'var(--color-bg-card-gradient, linear-gradient(to bottom, var(--color-border-muted), var(--color-border-muted)))',
                        border: workspace.status === 'flash'
                          ? '0.5px solid var(--color-accent-overlay)'
                          : '0.5px solid var(--color-bg-card-border, var(--color-border-muted))',
                        backdropFilter: 'blur(8px)',
                        WebkitBackdropFilter: 'blur(8px)',
                      }}
                    >
                      <div className="flex flex-col flex-grow gap-4">
                        <div className="flex items-center pr-10 overflow-hidden gap-2">
                          {workspace.status === 'flash' && (
                            <Zap className="h-4 w-4 flex-shrink-0" style={{ color: 'var(--color-accent-primary)' }} />
                          )}
                          <div className="font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                            {workspace.name}
                          </div>
                        </div>
                        <div className="text-sm line-clamp-3 flex-grow" style={{ color: 'var(--color-text-tertiary)' }}>
                          {workspace.description || ''}
                        </div>
                        <div className="text-xs mt-auto pt-3 flex justify-between" style={{ color: 'var(--color-text-tertiary)' }}>
                          <span>
                            Updated {workspace.updated_at ? new Date(workspace.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : t('workspace.recently')}
                          </span>
                        </div>
                      </div>
                    </div>
                    {/* Three dots menu */}
                    {workspace.status !== 'flash' && (
                      <div className="absolute top-3 right-3 z-10 transition-opacity opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(workspace);
                          }}
                          className="h-8 w-8 rounded-md transition-colors flex items-center justify-center"
                          style={{ color: 'var(--color-text-tertiary)' }}
                          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-border-muted)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ''; }}
                        >
                          <MoreHorizontal className="h-5 w-5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination dots — hidden during search */}
          {!isSearching && totalPages > 1 && (
            <MorphingPageDots
              totalPages={totalPages}
              activeIndex={currentPage}
              onChange={setCurrentPage}
            />
          )}
        </div>
      </main>

      {/* Create Workspace Modal */}
      <CreateWorkspaceModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreate={handleCreateWorkspace}
        onComplete={(wsId) => onWorkspaceSelect(wsId)}
      />

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={deleteModal.isOpen}
        workspaceName={deleteModal.workspace?.name || ''}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        isDeleting={isDeleting}
        error={deleteError}
      />
    </div>
  );
}

export default WorkspaceGallery;
