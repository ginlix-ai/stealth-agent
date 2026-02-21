import React from 'react';
import ChatInput from '../../../components/ui/chat-input';
import { useChatInput } from '../hooks/useChatInput';

/**
 * Chat input strip matching ChatAgent input bar.
 * When user sends a message, navigates to ChatAgent page with selected workspace.
 */
function ChatInputCard() {
  const {
    mode,
    setMode,
    isLoading,
    handleSend,
    workspaces,
    selectedWorkspaceId,
    setSelectedWorkspaceId,
  } = useChatInput();

  return (
    <ChatInput
      onSend={handleSend}
      disabled={isLoading}
      mode={mode}
      onModeChange={setMode}
      workspaces={workspaces}
      selectedWorkspaceId={selectedWorkspaceId}
      onWorkspaceChange={setSelectedWorkspaceId}
      placeholder="What would you like to know?"
    />
  );
}

export default ChatInputCard;
