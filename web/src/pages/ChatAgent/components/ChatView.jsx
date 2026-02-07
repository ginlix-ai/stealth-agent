import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, FolderOpen, Bot } from 'lucide-react';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { useChatMessages } from '../hooks/useChatMessages';
import { useFloatingCards } from '../hooks/useFloatingCards';
import FilePanel from './FilePanel';
import './FilePanel.css';
import ChatInput from './ChatInput';
import FloatingCard from './FloatingCard';
import FloatingCardIcon from './FloatingCardIcon';
import MessageList from './MessageList';
import TodoListCardContent from './TodoListCardContent';
import AgentPanel from './AgentPanel';
import TodoDrawer from './TodoDrawer';
import '../../Dashboard/Dashboard.css';

/**
 * ChatView Component
 * 
 * Displays the chat interface for a specific workspace and thread.
 * Handles:
 * - Message display and streaming
 * - Auto-scrolling
 * - Navigation back to thread gallery
 * - Auto-sending initial message from navigation state
 * 
 * @param {string} workspaceId - The workspace ID to chat in
 * @param {string} threadId - The thread ID to chat in
 * @param {Function} onBack - Callback to navigate back to thread gallery
 */
function ChatView({ workspaceId, threadId, onBack }) {
  const scrollAreaRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const initialMessageSentRef = useRef(false);
  const [filePanelTargetFile, setFilePanelTargetFile] = useState(null);
  const isDraggingRef = useRef(false);

  // Right panel management - can show 'file', 'agent', or null (closed)
  const [rightPanelType, setRightPanelType] = useState(null);
  const [rightPanelWidth, setRightPanelWidth] = useState(420);
  const [selectedAgentId, setSelectedAgentId] = useState(null);

  // Floating cards management - extracted to custom hook for better encapsulation
  // Must be called before useChatMessages since updateTodoListCard and updateSubagentCard are passed to it
  const {
    floatingCards,
    handleCardMinimize,
    handleCardMaximize,
    handleCardToggle,
    handleCardPositionChange,
    handleBringToFront,
    getMinimizedCards,
    getAllCards,
    updateTodoListCard,
    updateSubagentCard,
    inactivateAllSubagents,
    minimizeInactiveSubagents,
  } = useFloatingCards();

  // Chat messages management - receives updateTodoListCard and updateSubagentCard from floating cards hook
  const {
    messages,
    isLoading,
    isLoadingHistory,
    messageError,
    handleSendMessage,
    threadId: currentThreadId,
    getSubagentHistory,
  } = useChatMessages(workspaceId, threadId, updateTodoListCard, updateSubagentCard, inactivateAllSubagents, minimizeInactiveSubagents);

  // Convert floatingCards to agents array for AgentPanel
  const agents = Object.entries(floatingCards)
    .filter(([cardId]) => cardId.startsWith('subagent-'))
    .map(([cardId, card]) => ({
      id: cardId.replace('subagent-', ''),
      name: card.title || 'Agent',
      taskId: card.subagentData?.taskId || '',
      description: card.subagentData?.description || '',
      type: card.subagentData?.type || 'general-purpose',
      status: card.subagentData?.status || 'active',
      toolCalls: card.subagentData?.toolCalls || 0,
      currentTool: card.subagentData?.currentTool || '',
      messages: card.subagentData?.messages || [],
      isActive: card.subagentData?.isActive !== false,
    }));

  // Handle drag panel width
  const handleDividerMouseDown = useCallback((e) => {
    e.preventDefault();
    isDraggingRef.current = true;
    const startX = e.clientX;
    const startWidth = rightPanelWidth;

    const onMouseMove = (moveEvent) => {
      if (!isDraggingRef.current) return;
      const delta = startX - moveEvent.clientX;
      const newWidth = Math.max(280, Math.min(startWidth + delta, window.innerWidth * 0.6));
      setRightPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [rightPanelWidth]);

  // Open a file in the right panel from chat tool calls
  const handleOpenFileFromChat = useCallback((filePath) => {
    setRightPanelType('file');
    setFilePanelTargetFile(filePath);
  }, []);

  // Toggle file panel
  const handleToggleFilePanel = useCallback(() => {
    if (rightPanelType === 'file') {
      setRightPanelType(null);
    } else {
      setRightPanelType('file');
    }
  }, [rightPanelType]);

  // Toggle agent panel
  const handleToggleAgentPanel = useCallback(() => {
    if (rightPanelType === 'agent') {
      setRightPanelType(null);
      setSelectedAgentId(null);
    } else {
      setRightPanelType('agent');
      // Auto-select first agent if available
      if (agents.length > 0 && !selectedAgentId) {
        setSelectedAgentId(agents[0].id);
      }
    }
  }, [rightPanelType, agents, selectedAgentId]);

  // Handle agent selection
  const handleSelectAgent = useCallback((agentId) => {
    setSelectedAgentId(agentId);
    if (agentId !== null) {
      setRightPanelType('agent');
    }
  }, []);

  // Handle removing an agent
  const handleRemoveAgent = useCallback((agentId) => {
    // Remove the agent's floating card
    const cardId = `subagent-${agentId}`;
    handleCardMinimize(cardId); // This will remove it from view

    // If the removed agent was selected, select another agent
    if (selectedAgentId === agentId) {
      const remainingAgents = agents.filter(a => a.id !== agentId);
      if (remainingAgents.length > 0) {
        // Select the first remaining agent and keep agent panel open
        setSelectedAgentId(remainingAgents[0].id);
        setRightPanelType('agent');
      } else {
        // No more agents, clear selection but don't close panel immediately
        setSelectedAgentId(null);
      }
    }
  }, [selectedAgentId, agents, handleCardMinimize]);

  // Auto-open agent panel when a new agent starts working
  useEffect(() => {
    if (agents.length > 0) {
      // If there are agents but panel is not open, open it
      if (rightPanelType !== 'agent') {
        setRightPanelType('agent');
      }
      // If no agent is selected, select the first one
      if (!selectedAgentId) {
        setSelectedAgentId(agents[0].id);
      }
    }
  }, [agents.length]); // Only trigger when the number of agents changes

  // Update URL when thread ID changes (e.g., when __default__ becomes actual thread ID)
  // This triggers a re-render with the new threadId, which will then load history
  useEffect(() => {
    if (currentThreadId && currentThreadId !== '__default__' && currentThreadId !== threadId && workspaceId) {
      console.log('[ChatView] Thread ID changed from', threadId, 'to', currentThreadId, '- updating URL');
      // Update URL to reflect the actual thread ID
      // This will cause ChatAgent to re-render with new threadId prop, triggering history load
      navigate(`/chat/${workspaceId}/${currentThreadId}`, { replace: true });
    }
  }, [currentThreadId, threadId, workspaceId, navigate]);

  // Auto-send initial message from navigation state (e.g., from Dashboard)
  useEffect(() => {
    // Only proceed if we have the required IDs
    if (!workspaceId || !threadId) {
      return;
    }

    // Handle onboarding flow
    if (location.state?.isOnboarding && !initialMessageSentRef.current && !isLoading && !isLoadingHistory) {
      initialMessageSentRef.current = true;
      // Clear navigation state to prevent re-sending on re-renders
      navigate(location.pathname, { replace: true, state: {} });
      // Small delay to ensure component is fully mounted
      setTimeout(() => {
        const onboardingMessage = "Hi! I am new here and would like to set up my profile.";
        const additionalContext = [
          {
            type: "skills",
            name: "user-profile",
            instruction: "Help the user with first time onboarding. Reference the skills/user-profile/onboarding.md for details. You should use load_skill tool to load the user-profile skill before calling any of the tools."
          }
        ];
        handleSendMessage(onboardingMessage, false, additionalContext);
      }, 100);
      return;
    }
    
    // Handle regular message flow
    if (location.state?.initialMessage && !initialMessageSentRef.current) {
      // For new threads (__default__), send immediately without waiting for history
      // For existing threads, wait for history to finish loading
      if (threadId === '__default__') {
        // New thread - send immediately
        initialMessageSentRef.current = true;
        // Clear navigation state to prevent re-sending on re-renders
        navigate(location.pathname, { replace: true, state: {} });
        // Small delay to ensure component is fully mounted
        setTimeout(() => {
          const { initialMessage, planMode } = location.state;
          handleSendMessage(initialMessage, planMode || false);
        }, 100);
      } else if (!isLoadingHistory && !isLoading) {
        // Existing thread - wait for history to load, then send
        // This ensures we don't send duplicate messages
        initialMessageSentRef.current = true;
        // Clear navigation state to prevent re-sending on re-renders
        navigate(location.pathname, { replace: true, state: {} });
        // Small delay to ensure component is fully mounted
        setTimeout(() => {
          const { initialMessage, planMode } = location.state;
          handleSendMessage(initialMessage, planMode || false);
        }, 100);
      }
    }
  }, [location.state, workspaceId, threadId, isLoading, isLoadingHistory, handleSendMessage, navigate, location.pathname]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      // ScrollArea component has a nested structure with overflow-auto
      const scrollContainer = scrollAreaRef.current.querySelector('.overflow-auto') ||
                             scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]') ||
                             scrollAreaRef.current;
      if (scrollContainer) {
        // Use setTimeout to ensure DOM is updated
        setTimeout(() => {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }, 0);
      }
    }
  }, [messages]);


  // Early return if workspaceId or threadId is missing
  if (!workspaceId || !threadId) {
    return (
      <div className="flex items-center justify-center h-full" style={{ backgroundColor: '#1B1D25' }}>
        <p className="text-sm" style={{ color: '#FFFFFF', opacity: 0.65 }}>
          Missing workspace or thread information
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex h-screen w-full overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-page)',
      }}
    >
      {/* Left Side: Topbar + Chat Window (Vertical) */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 min-w-0 flex-shrink-0">
          <div className="flex items-center gap-4 min-w-0 flex-shrink">
            <button
              onClick={onBack}
              className="p-2 rounded-md transition-colors hover:bg-white/10 flex-shrink-0"
              style={{ color: '#FFFFFF' }}
              title="Back to threads"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="text-lg font-semibold whitespace-nowrap dashboard-title-font" style={{ color: '#FFFFFF' }}>
              Chat Agent
            </h1>
            {isLoadingHistory && (
              <span className="text-xs whitespace-nowrap" style={{ color: '#FFFFFF', opacity: 0.5 }}>
                Loading history...
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleToggleFilePanel}
              className={`p-2 rounded-md transition-colors ${rightPanelType === 'file' ? 'bg-white/15' : 'hover:bg-white/10'}`}
              style={{ color: '#FFFFFF' }}
              title="Workspace Files"
            >
              <FolderOpen className="h-5 w-5" />
            </button>
            <button
              onClick={handleToggleAgentPanel}
              className={`p-2 rounded-md transition-colors ${rightPanelType === 'agent' ? 'bg-white/15' : 'hover:bg-white/10'}`}
              style={{ color: '#FFFFFF' }}
              title="Agents"
            >
              <Bot className="h-5 w-5" />
            </button>
            {/* Floating card icons for non-agent and non-todolist cards */}
            {getAllCards()
              .filter(([cardId]) => !cardId.startsWith('subagent-') && cardId !== 'todo-list-card')
              .map(([cardId, card]) => (
                <FloatingCardIcon
                  key={cardId}
                  id={cardId}
                  title={card.title || 'Card'}
                  onClick={() => handleCardToggle(cardId)}
                  hasUnreadUpdate={card.hasUnreadUpdate || false}
                  isActive={true}
                />
              ))}
          </div>
        </div>

        {/* Chat Window */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages Area - Fixed height, scrollable */}
          <div
            className="flex-1 overflow-hidden"
            style={{
              minHeight: 0,
              height: 0, // Force flex-1 to work properly
            }}
          >
            <ScrollArea ref={scrollAreaRef} className="h-full w-full">
              <div className="px-6 py-4 flex justify-center">
                <div className="w-full max-w-3xl">
                  <MessageList
                  messages={messages}
                  onOpenFile={handleOpenFileFromChat}
                  onOpenSubagentTask={(subagentInfo) => {
                    console.log('[ChatView] onOpenSubagentTask called with:', subagentInfo);
                    const { subagentId, description, type, status } = subagentInfo;

                    if (!updateSubagentCard) {
                      console.error('[ChatView] updateSubagentCard is not defined!');
                      return;
                    }

                    // Try to load history for this subagent (if available)
                    const history = getSubagentHistory
                      ? getSubagentHistory(subagentId)
                      : null;

                    const finalDescription = history?.description || description || '';
                    const finalType = history?.type || type || 'general-purpose';
                    const finalStatus = history?.status || status || 'unknown';
                    const finalMessages = history?.messages || [];

                    console.log('[ChatView] Opening subagent in agent panel:', {
                      subagentId,
                      hasHistory: !!history,
                      messagesCount: finalMessages.length,
                    });

                    // Update the floating card data (for data management)
                    updateSubagentCard(subagentId, {
                      taskId: subagentId,
                      description: finalDescription,
                      type: finalType,
                      status: finalStatus,
                      toolCalls: 0,
                      currentTool: '',
                      messages: finalMessages,
                      isHistory: !!history,
                      isActive: !history,
                    });

                    // Open agent panel and select this agent
                    setRightPanelType('agent');
                    setSelectedAgentId(subagentId);
                  }}
                />
                </div>
              </div>
            </ScrollArea>
          </div>

          {/* Input Area */}
          <div className="flex-shrink-0 p-4 flex justify-center">
            <div className="w-full max-w-3xl space-y-3">
              <TodoDrawer todoData={floatingCards['todo-list-card']?.todoData} />
              <ChatInput onSend={handleSendMessage} disabled={isLoading || isLoadingHistory || !workspaceId} />
            </div>
          </div>
        </div>
      </div>

      {/* Right Side: Split Panel (File or Agent) */}
      {rightPanelType && (
        <>
          <div
            className="chat-split-divider"
            onMouseDown={handleDividerMouseDown}
          />
          <div className="flex-shrink-0" style={{ width: rightPanelWidth }}>
            {rightPanelType === 'file' ? (
              <FilePanel
                workspaceId={workspaceId}
                onClose={() => setRightPanelType(null)}
                targetFile={filePanelTargetFile}
                onTargetFileHandled={() => setFilePanelTargetFile(null)}
              />
            ) : rightPanelType === 'agent' ? (
              <div className="h-full p-4" style={{ backgroundColor: 'transparent', borderLeft: '1px solid rgba(255, 255, 255, 0.1)' }}>
                <AgentPanel
                  agents={agents}
                  selectedAgentId={selectedAgentId}
                  onSelectAgent={handleSelectAgent}
                  onClose={() => setRightPanelType(null)}
                  onRemoveAgent={handleRemoveAgent}
                />
              </div>
            ) : null}
          </div>
        </>
      )}

      {/* Floating Cards - Only for non-agent cards */}
      {Object.entries(floatingCards)
        .filter(([cardId]) => !cardId.startsWith('subagent-') && cardId !== 'todo-list-card')
        .map(([cardId, card]) => (
          <FloatingCard
            key={cardId}
            id={cardId}
            title={card.title || 'Card'}
            isMinimized={card.isMinimized}
            onMinimize={() => handleCardMinimize(cardId)}
            onMaximize={() => handleCardMaximize(cardId)}
            initialPosition={card.position}
            onPositionChange={handleCardPositionChange}
            zIndex={card.zIndex || 50}
            onBringToFront={handleBringToFront}
          >
            {cardId === 'todo-list-card' && card.todoData ? (
              <TodoListCardContent
                todos={card.todoData.todos}
                total={card.todoData.total}
                completed={card.todoData.completed}
                in_progress={card.todoData.in_progress}
                pending={card.todoData.pending}
              />
            ) : (
              <div className="text-sm" style={{ color: '#FFFFFF' }}>
                <p className="mb-2">This is {card.title}.</p>
                <p className="mb-2">You can drag this card by clicking and dragging the header.</p>
                <p className="mb-2">Click anywhere on the card to bring it to the front.</p>
                <p className="mb-2">Click the minimize button to minimize it to an icon in the top bar.</p>
                <p>Click the bookmark icon in the top bar to restore it.</p>
              </div>
            )}
          </FloatingCard>
        ))}
    </div>
  );
}

export default ChatView;
