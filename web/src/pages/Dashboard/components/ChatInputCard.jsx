import React from 'react';
import { ChevronDown, Globe, Plus, Send, Zap } from 'lucide-react';
import { Card, CardContent } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';

/**
 * Chat input strip. No data props; placeholder for future handlers.
 */
function ChatInputCard() {
  return (
    <Card
      className="fin-card flex-shrink-0"
      style={{ borderColor: 'var(--color-accent-primary)', borderWidth: '1.5px' }}
    >
      <CardContent className="p-3">
        <div className="flex items-center gap-1">
          <button className="w-9 h-9 flex items-center justify-center rounded-md transition-colors">
            <Plus className="h-4 w-4" style={{ color: 'var(--color-text-muted)' }} />
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
          />
          <div className="flex items-center gap-1">
            <button className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors">
              <Globe className="h-4 w-4" style={{ color: 'var(--color-text-muted)' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Agent
              </span>
            </button>
            <button
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors"
              style={{ backgroundColor: 'var(--color-border-muted)' }}
            >
              <Zap className="h-4 w-4" style={{ color: 'var(--color-text-muted)' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Fast
              </span>
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors">
              <span className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Tool
              </span>
              <ChevronDown className="h-4 w-4" style={{ color: 'var(--color-text-muted)' }} />
            </button>
            <button
              className="w-8 h-9 rounded-md flex items-center justify-center transition-colors"
              style={{ backgroundColor: 'var(--color-accent-primary)' }}
            >
              <Send className="h-4 w-4" style={{ color: 'var(--color-text-on-accent)' }} />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default ChatInputCard;
