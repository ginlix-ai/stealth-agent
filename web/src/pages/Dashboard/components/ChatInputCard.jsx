import React, { useState } from 'react';
import { ChevronDown, Globe, Plus, Send, Zap } from 'lucide-react';
import { Card, CardContent } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { useNavigate } from 'react-router-dom';
import { getWorkspaces, DEFAULT_USER_ID } from '../../ChatAgent/utils/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../../components/ui/dialog';
import { useToast } from '../../../components/ui/use-toast';

/**
 * Chat input strip matching ChatAgent input bar.
 * When user sends a message, navigates to ChatAgent page with first workspace.
 */
function ChatInputCard() {
  const [message, setMessage] = useState('');
  const [planMode, setPlanMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showNoWorkspaceDialog, setShowNoWorkspaceDialog] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSend = async () => {
    if (!message.trim() || isLoading) {
      return;
    }

    setIsLoading(true);
    try {
      // Fetch user's workspaces
      const { workspaces } = await getWorkspaces(DEFAULT_USER_ID);
      
      if (!workspaces || workspaces.length === 0) {
        // Show popup if no workspace exists
        setShowNoWorkspaceDialog(true);
        setIsLoading(false);
        return;
      }

      // Get first workspace
      const firstWorkspace = workspaces[0];
      const workspaceId = firstWorkspace.workspace_id;

      // Navigate to ChatAgent page with workspace and message in state
      navigate(`/chat/${workspaceId}`, {
        state: {
          initialMessage: message.trim(),
          planMode: planMode,
        },
      });
      
      // Clear input
      setMessage('');
    } catch (error) {
      console.error('Error fetching workspaces:', error);
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to fetch workspaces. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <Card
        className="fin-card flex-shrink-0"
        style={{ borderColor: 'var(--color-accent-primary)', borderWidth: '1.5px' }}
      >
        <CardContent className="p-3">
          <div className="flex items-center gap-1">
            <button 
              className="w-9 h-9 flex items-center justify-center rounded-md transition-colors hover:bg-white/5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <Plus className="h-4 w-4" />
            </button>
            <Input
              placeholder="What would you like to know?"
              className="flex-1 h-9 rounded-md text-sm focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
              style={{
                backgroundColor: 'transparent',
                border: 'none',
                color: 'var(--color-text-muted)',
                fontSize: '14px',
                outline: 'none',
              }}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
            <div className="flex items-center gap-1">
              <button 
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors hover:bg-white/5"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <Globe className="h-4 w-4" />
                <span className="text-sm font-medium">Agent</span>
              </button>
              <button
                className={`flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors ${
                  planMode ? 'bg-white/100' : 'hover:bg-white/5'
                }`}
                style={{ color: 'var(--color-text-muted)' }}
                onClick={() => setPlanMode(!planMode)}
              >
                <Zap className="h-4 w-4" />
                <span className="text-sm font-medium">Plan Mode</span>
              </button>
              <button 
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors hover:bg-white/5"
                style={{ color: 'var(--color-text-muted)' }}
              >
                <span className="text-sm font-medium">Tool</span>
                <ChevronDown className="h-4 w-4" />
              </button>
              <button
                className="w-8 h-9 rounded-md flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ 
                  backgroundColor: (isLoading || !message.trim()) ? 'rgba(97, 85, 245, 0.5)' : 'var(--color-accent-primary)',
                  color: 'var(--color-text-on-accent)',
                }}
                onClick={handleSend}
                disabled={isLoading || !message.trim()}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* No Workspace Dialog */}
      <Dialog open={showNoWorkspaceDialog} onOpenChange={setShowNoWorkspaceDialog}>
        <DialogContent className="sm:max-w-md text-white border" style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}>
          <DialogHeader>
            <DialogTitle className="dashboard-title-font" style={{ color: 'var(--color-text-primary)' }}>
              No Workspace Found
            </DialogTitle>
            <DialogDescription style={{ color: 'var(--color-text-secondary)' }}>
              You need to create a workspace before you can start chatting. Please go to the Chat Agent page to create one.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={() => setShowNoWorkspaceDialog(false)}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors hover:bg-white/10"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Close
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNoWorkspaceDialog(false);
                navigate('/chat');
              }}
              className="px-4 py-2 rounded-md text-sm font-medium transition-colors hover:opacity-90"
              style={{ backgroundColor: 'var(--color-accent-primary)', color: 'var(--color-text-on-accent)' }}
            >
              Go to Chat Agent
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default ChatInputCard;
