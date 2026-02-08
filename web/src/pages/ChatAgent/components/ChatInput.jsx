import ChatInput from '../../../components/ui/ChatInput';

/**
 * ChatInput wrapper for ChatAgent page
 * Uses uncontrolled mode - component manages its own state
 */
const ChatInputWrapper = ({ onSend, disabled = false }) => {
  return (
    <ChatInput
      onSend={onSend}
      disabled={disabled}
      variant="chat"
    />
  );
};

export default ChatInputWrapper;
