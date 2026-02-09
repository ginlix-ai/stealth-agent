import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { Send, Loader2, Square, Zap, FileText, X } from 'lucide-react';
import './ChatInputWithMentions.css';

/**
 * ChatInputWithMentions
 *
 * Textarea-based chat input with @ file mention autocomplete.
 * When user types @, a dropdown appears showing workspace files
 * filtered by the partial path typed after @.
 *
 * @param {Function} onSend - (message, planMode, mentionedFiles) => void
 * @param {boolean} disabled
 * @param {boolean} isLoading
 * @param {Function} onStop
 * @param {string[]} files - workspace file paths from useWorkspaceFiles
 */
function ChatInputWithMentions({ onSend, disabled = false, isLoading = false, onStop, files = [] }) {
  const [message, setMessage] = useState('');
  const [planMode, setPlanMode] = useState(false);
  const [mentionedFiles, setMentionedFiles] = useState([]); // array of { path: string }

  // Autocomplete state
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [autocompleteQuery, setAutocompleteQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [mentionStart, setMentionStart] = useState(-1); // character index of the '@'

  // Stop button state
  const [isStopping, setIsStopping] = useState(false);

  const textareaRef = useRef(null);
  const autocompleteRef = useRef(null);

  // Reset isStopping when loading finishes
  useEffect(() => {
    if (!isLoading) setIsStopping(false);
  }, [isLoading]);

  const handleStop = useCallback(() => {
    if (isStopping) return;
    setIsStopping(true);
    onStop?.();
  }, [isStopping, onStop]);

  // Filtered files for autocomplete — sorted: root → results/ → data/ → other
  const filteredFiles = useMemo(() => {
    if (!showAutocomplete) return [];
    const query = autocompleteQuery.toLowerCase();
    const dirPriority = { '': 0, 'results': 1, 'data': 2 };
    return files
      .filter((f) => f.toLowerCase().includes(query))
      .sort((a, b) => {
        const da = a.includes('/') ? a.slice(0, a.indexOf('/')) : '';
        const db = b.includes('/') ? b.slice(0, b.indexOf('/')) : '';
        const pa = dirPriority[da] ?? 3;
        const pb = dirPriority[db] ?? 3;
        if (pa !== pb) return pa - pb;
        return a.localeCompare(b);
      })
      .slice(0, 10);
  }, [files, autocompleteQuery, showAutocomplete]);

  // Reset active index when filtered results change
  useEffect(() => {
    setActiveIndex(0);
  }, [filteredFiles.length]);

  // Detect @ trigger on input change
  const handleChange = useCallback((e) => {
    const val = e.target.value;
    setMessage(val);

    const cursorPos = e.target.selectionStart;
    // Scan backward from cursor for @ preceded by whitespace or start-of-input
    let atIdx = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      const ch = val[i];
      if (ch === '@') {
        // Valid if at start of input or preceded by whitespace
        if (i === 0 || /\s/.test(val[i - 1])) {
          atIdx = i;
        }
        break;
      }
      // Stop scanning if we hit whitespace (no @ found in this "word")
      if (/\s/.test(ch)) break;
    }

    if (atIdx >= 0) {
      const partial = val.slice(atIdx + 1, cursorPos);
      setMentionStart(atIdx);
      setAutocompleteQuery(partial);
      setShowAutocomplete(true);
    } else {
      setShowAutocomplete(false);
      setMentionStart(-1);
      setAutocompleteQuery('');
    }
  }, []);

  // Insert selected file into textarea
  const selectFile = useCallback((filePath) => {
    if (mentionStart < 0) return;

    const cursorPos = textareaRef.current?.selectionStart ?? message.length;
    // Replace from @ to cursor with the file path
    const before = message.slice(0, mentionStart);
    const after = message.slice(cursorPos);
    const newMessage = before + '@' + filePath + ' ' + after;
    setMessage(newMessage);

    // Add to mentioned files (deduplicate)
    setMentionedFiles((prev) => {
      if (prev.some((f) => f.path === filePath)) return prev;
      return [...prev, { path: filePath }];
    });

    // Close autocomplete
    setShowAutocomplete(false);
    setMentionStart(-1);
    setAutocompleteQuery('');

    // Refocus textarea and set cursor after inserted path
    setTimeout(() => {
      if (textareaRef.current) {
        const newCursorPos = before.length + 1 + filePath.length + 1;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
      }
    }, 0);
  }, [mentionStart, message]);

  // Remove a mention pill
  const removeMention = useCallback((path) => {
    setMentionedFiles((prev) => prev.filter((f) => f.path !== path));
  }, []);

  // Send message
  const handleSend = useCallback(() => {
    if (!message.trim() || disabled) return;
    onSend(message, planMode);
    setMessage('');
    setMentionedFiles([]);
    setShowAutocomplete(false);
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [message, disabled, onSend, planMode, mentionedFiles]);

  // Keyboard handling
  const handleKeyDown = useCallback((e) => {
    if (showAutocomplete && filteredFiles.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % filteredFiles.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => (prev - 1 + filteredFiles.length) % filteredFiles.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        selectFile(filteredFiles[activeIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowAutocomplete(false);
        return;
      }
    }

    // Normal enter to send (not shift+enter)
    if (e.key === 'Enter' && !e.shiftKey && !showAutocomplete) {
      e.preventDefault();
      handleSend();
    }

    // Escape to dismiss autocomplete even with no results
    if (e.key === 'Escape' && showAutocomplete) {
      setShowAutocomplete(false);
    }
  }, [showAutocomplete, filteredFiles, activeIndex, selectFile, handleSend]);

  // Auto-grow textarea
  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, []);

  // Scroll active autocomplete item into view
  useEffect(() => {
    if (!showAutocomplete || !autocompleteRef.current) return;
    const items = autocompleteRef.current.querySelectorAll('.mention-autocomplete-item');
    if (items[activeIndex]) {
      items[activeIndex].scrollIntoView({ block: 'nearest' });
    }
  }, [activeIndex, showAutocomplete]);

  // Close autocomplete on blur (with delay so clicks register)
  const handleBlur = useCallback(() => {
    setTimeout(() => {
      setShowAutocomplete(false);
    }, 200);
  }, []);

  return (
    <div className="mention-input-container">
      {/* Mention pills */}
      {mentionedFiles.length > 0 && (
        <div className="mention-pills">
          {mentionedFiles.map((f) => {
            const name = f.path.split('/').pop();
            return (
              <div key={f.path} className="mention-pill" title={f.path}>
                <FileText className="h-3 w-3 flex-shrink-0" style={{ color: 'rgba(97, 85, 245, 0.8)' }} />
                <span>{name}</span>
                <button
                  className="mention-pill-remove"
                  onClick={() => removeMention(f.path)}
                  title="Remove"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Autocomplete dropdown (above textarea) */}
      {showAutocomplete && (
        <div className="mention-autocomplete" ref={autocompleteRef}>
          {filteredFiles.length === 0 ? (
            <div className="mention-autocomplete-empty">
              {files.length === 0 ? 'No files available' : 'No matching files'}
            </div>
          ) : (
            filteredFiles.map((filePath, idx) => {
              const name = filePath.split('/').pop();
              const dir = filePath.includes('/') ? filePath.slice(0, filePath.lastIndexOf('/')) : '';
              return (
                <div
                  key={filePath}
                  className={`mention-autocomplete-item ${idx === activeIndex ? 'active' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault(); // prevent blur
                    selectFile(filePath);
                  }}
                  onMouseEnter={() => setActiveIndex(idx)}
                >
                  <FileText className="h-4 w-4 flex-shrink-0" style={{ color: 'rgba(255,255,255,0.45)' }} />
                  <span className="file-name">{name}</span>
                  {dir && <span className="file-path">{dir}/</span>}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        className="mention-textarea"
        placeholder="What would you like to know? Type @ to mention a file"
        value={message}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        onBlur={handleBlur}
        disabled={disabled}
        rows={1}
      />

      {/* Bottom row: Plan Mode toggle + Send/Stop */}
      <div className="mention-input-actions">
        <button
          className={`inline-flex items-center rounded-full border-none cursor-pointer${planMode ? ' plan-mode-toggle-active' : ''}`}
          style={{
            gap: '6px',
            padding: '6px 10px',
            fontSize: '13px',
            fontWeight: 500,
            background: planMode ? 'rgba(97, 85, 245, 0.25)' : 'transparent',
            color: planMode ? '#a89afb' : 'var(--color-text-muted, #8b8fa3)',
            border: planMode ? '1px solid rgba(97, 85, 245, 0.5)' : '1px solid transparent',
            transition: 'background 0.2s, color 0.2s, border-color 0.2s',
          }}
          onClick={() => setPlanMode(!planMode)}
          onMouseEnter={(e) => {
            if (!planMode) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
          }}
          onMouseLeave={(e) => {
            if (!planMode) e.currentTarget.style.background = 'transparent';
          }}
        >
          <Zap className="h-4 w-4" style={planMode ? { fill: '#6155F5', color: '#a89afb' } : {}} />
          <span>Plan Mode</span>
        </button>

        {isLoading && onStop ? (
          <button
            className="w-8 h-9 rounded-md flex items-center justify-center transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ backgroundColor: isStopping ? '#991b1b' : '#dc2626', color: '#FFFFFF' }}
            onClick={handleStop}
            disabled={isStopping}
            title={isStopping ? 'Stopping...' : 'Stop'}
          >
            {isStopping ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Square className="h-3.5 w-3.5" fill="currentColor" />
            )}
          </button>
        ) : (
          <button
            className="w-8 h-9 rounded-md flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: disabled || !message.trim() ? 'rgba(97, 85, 245, 0.5)' : '#6155F5',
              color: '#FFFFFF',
            }}
            onClick={handleSend}
            disabled={disabled || !message.trim()}
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export default ChatInputWithMentions;
