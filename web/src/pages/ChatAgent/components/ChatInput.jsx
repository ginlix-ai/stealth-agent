import { Plus, Send } from 'lucide-react';
import { useState } from 'react';
import { Input } from '../../../components/ui/input';

const ChatInput = ({ onSend, disabled = false }) => {
  const [message, setMessage] = useState('');

  const handleSend = () => {
    if (!message.trim() || disabled) {
      return;
    }

    onSend(message, false); // Always use planMode = false
    setMessage(''); // Clear input after sending
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="flex items-center gap-2 p-3 rounded-lg"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        border: '1.5px solid hsl(var(--primary))',
      }}
    >
      <button 
        className="w-9 h-9 flex items-center justify-center rounded-md transition-colors hover:bg-white/5"
        style={{ color: '#BBBBBB' }}
      >
        <Plus className="h-4 w-4" />
      </button>
      <Input 
        placeholder="What would you like to know?" 
        className="flex-1 h-9 rounded-md text-sm focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
        style={{ 
          backgroundColor: 'transparent',
          border: 'none',
          color: '#BBBBBB',
          fontSize: '14px',
        }}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyPress={handleKeyPress}
        disabled={disabled}
      />
      <button
        className="w-8 h-9 rounded-md flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          backgroundColor: disabled ? 'rgba(97, 85, 245, 0.5)' : '#6155F5',
          color: '#FFFFFF',
        }}
        onClick={handleSend}
        disabled={disabled || !message.trim()}
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  );
};

export default ChatInput;
