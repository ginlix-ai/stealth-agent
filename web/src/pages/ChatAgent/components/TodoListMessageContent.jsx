import React, { useState, useEffect, useRef } from 'react';
import { ListTodo, CheckCircle2, Circle, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * TodoListMessageContent Component
 * 
 * Renders todo list updates from artifact events with artifact_type: "todo_update".
 * 
 * Features:
 * - Shows todo list icon
 * - Displays all todo items with their status
 * - Different icons for different statuses (pending, in_progress, completed)
 * - Expanded by default (unlike reasoning/tool calls)
 * - Clickable to fold/unfold content
 * - Shows status counts (total, completed, in_progress, pending)
 * 
 * @param {Object} props
 * @param {Array} props.todos - Array of todo items
 * @param {number} props.total - Total number of todos
 * @param {number} props.completed - Number of completed todos
 * @param {number} props.in_progress - Number of in-progress todos
 * @param {number} props.pending - Number of pending todos
 */
function TodoListMessageContent({ todos, total, completed, in_progress, pending }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const wasAllCompleted = useRef(false);

  // Auto-collapse when all todos become completed
  useEffect(() => {
    const allCompleted = total > 0 && completed === total;
    if (allCompleted && !wasAllCompleted.current) {
      setIsExpanded(false);
    }
    wasAllCompleted.current = allCompleted;
  }, [completed, total]);

  // Don't render if there are no todos
  if (!todos || todos.length === 0) {
    console.warn('[TodoListMessageContent] No todos to render, returning null');
    return null;
  }

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
  };

  /**
   * Get icon for todo item based on status
   * @param {string} status - Todo item status
   * @returns {React.Component} Icon component
   */
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4" style={{ color: '#0FEDBE' }} />;
      case 'in_progress':
        return <Loader2 className="h-4 w-4 animate-spin" style={{ color: '#6155F5' }} />;
      case 'pending':
      default:
        return <Circle className="h-4 w-4" style={{ color: '#FFFFFF', opacity: 0.5 }} />;
    }
  };

  /**
   * Get status label with appropriate styling
   * @param {string} status - Todo item status
   * @returns {string} Formatted status label
   */
  const getStatusLabel = (status) => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'in_progress':
        return 'In Progress';
      case 'pending':
        return 'Pending';
      default:
        return status;
    }
  };

  /**
   * Get status badge color
   * @param {string} status - Todo item status
   * @returns {string} Background color for status badge
   */
  const getStatusBadgeColor = (status) => {
    switch (status) {
      case 'completed':
        return 'rgba(15, 237, 190, 0.2)';
      case 'in_progress':
        return 'rgba(97, 85, 245, 0.2)';
      case 'pending':
        return 'rgba(255, 255, 255, 0.1)';
      default:
        return 'rgba(255, 255, 255, 0.1)';
    }
  };

  return (
    <div className="mt-2">
      {/* Todo list indicator button */}
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md transition-colors hover:bg-white/10 w-full"
        style={{
          backgroundColor: 'rgba(97, 85, 245, 0.15)',
          border: '1px solid rgba(97, 85, 245, 0.3)',
        }}
        title="Todo List"
      >
        {/* Icon */}
        <ListTodo className="h-4 w-4" style={{ color: '#6155F5' }} />
        
        {/* Label with counts */}
        <span className="text-xs font-medium" style={{ color: '#FFFFFF', opacity: 0.9 }}>
          Todo List
        </span>
        
        {/* Status summary */}
        <span className="text-xs ml-auto" style={{ color: '#FFFFFF', opacity: 0.6 }}>
          {completed}/{total} completed
        </span>
        
        {/* Expand/collapse icon */}
        {isExpanded ? (
          <ChevronUp className="h-3 w-3" style={{ color: '#FFFFFF', opacity: 0.6 }} />
        ) : (
          <ChevronDown className="h-3 w-3" style={{ color: '#FFFFFF', opacity: 0.6 }} />
        )}
      </button>

      {/* Todo list content (shown when expanded) */}
      {isExpanded && (
        <div
          className="mt-2 space-y-2"
          style={{
            backgroundColor: 'rgba(97, 85, 245, 0.1)',
            border: '1px solid rgba(97, 85, 245, 0.2)',
            borderRadius: '6px',
            padding: '12px',
          }}
        >
          {/* Status summary bar */}
          <div className="flex items-center gap-4 pb-2 mb-2" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <div className="text-xs" style={{ color: '#FFFFFF', opacity: 0.7 }}>
              <span className="font-semibold">Total:</span> {total}
            </div>
            <div className="text-xs" style={{ color: '#0FEDBE', opacity: 0.9 }}>
              <span className="font-semibold">Completed:</span> {completed}
            </div>
            <div className="text-xs" style={{ color: '#6155F5', opacity: 0.9 }}>
              <span className="font-semibold">In Progress:</span> {in_progress}
            </div>
            <div className="text-xs" style={{ color: '#FFFFFF', opacity: 0.6 }}>
              <span className="font-semibold">Pending:</span> {pending}
            </div>
          </div>

          {/* Todo items list */}
          <div className="space-y-2">
            {todos.map((todo, index) => (
              <div
                key={`todo-${index}-${todo.activeForm || index}`}
                className="flex items-start gap-3 p-2 rounded-md"
                style={{
                  backgroundColor: getStatusBadgeColor(todo.status),
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                {/* Status icon */}
                <div className="flex-shrink-0 mt-0.5">
                  {getStatusIcon(todo.status)}
                </div>

                {/* Todo content */}
                <div className="flex-1 min-w-0">
                  {/* Todo name (activeForm) */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold" style={{ color: '#FFFFFF', opacity: 0.9 }}>
                      {todo.activeForm || `Task ${index + 1}`}
                    </span>
                    {/* Status badge */}
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: getStatusBadgeColor(todo.status),
                        color: '#FFFFFF',
                        opacity: 0.8,
                      }}
                    >
                      {getStatusLabel(todo.status)}
                    </span>
                  </div>

                  {/* Todo content/description */}
                  {todo.content && (
                    <p className="text-xs" style={{ color: '#FFFFFF', opacity: 0.7 }}>
                      {todo.content}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default TodoListMessageContent;
