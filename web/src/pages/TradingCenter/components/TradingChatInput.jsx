import React from 'react';
import { ChevronDown, Globe, Plus, Send, Zap, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { useChatInput } from '../../Dashboard/hooks/useChatInput';
import './TradingChatInput.css';

/**
 * Chat input for TradingCenter right panel.
 * Same layout as Dashboard: Plus, input "What would you like to know?", Agent, Plan Mode, Tool, Send.
 */
function TradingChatInput() {
  const {
    message,
    setMessage,
    planMode,
    setPlanMode,
    isLoading,
    showCreatingDialog,
    handleSend,
    handleKeyPress,
  } = useChatInput();

  return (
    <>
      <div className="trading-chat-card">
        <div className="trading-chat-row">
          <button
            type="button"
            className="trading-chat-btn trading-chat-btn-icon"
            aria-label="Add"
          >
            <Plus className="trading-chat-icon" />
          </button>
          <Input
            className="trading-chat-input"
            placeholder="What would you like to know?"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleKeyPress(e);
              }
            }}
            disabled={isLoading}
          />
          <div className="trading-chat-actions">
            <button type="button" className="trading-chat-btn trading-chat-btn-pill">
              <Globe className="trading-chat-icon-sm" />
              <span>Agent</span>
            </button>
            <button
              type="button"
              className={`trading-chat-btn trading-chat-btn-pill ${planMode ? 'active' : ''}`}
              onClick={() => setPlanMode(!planMode)}
            >
              <Zap className="trading-chat-icon-sm" />
              <span>Plan Mode</span>
            </button>
            <button type="button" className="trading-chat-btn trading-chat-btn-pill trading-chat-btn-tool">
              <span>Tool</span>
              <ChevronDown className="trading-chat-icon-sm" />
            </button>
            <button
              type="button"
              className="trading-chat-send"
              onClick={handleSend}
              disabled={isLoading || !message.trim()}
              aria-label="Send"
            >
              {isLoading ? (
                <Loader2 className="trading-chat-send-icon spinning" />
              ) : (
                <Send className="trading-chat-send-icon" />
              )}
            </button>
          </div>
        </div>
      </div>

      <Dialog open={showCreatingDialog} onOpenChange={() => {}}>
        <DialogContent
          className="sm:max-w-md text-white border"
          style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}
        >
          <DialogHeader>
            <DialogTitle className="dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
              Creating Workspace
            </DialogTitle>
            <DialogDescription style={{ color: 'var(--color-text-secondary)' }}>
              Creating your default "Stealth Agent" workspace. Please wait...
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--color-accent-primary)' }} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default TradingChatInput;
