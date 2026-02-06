import React from 'react';
import { ListTodo, CheckCircle2, Circle, Loader2 } from 'lucide-react';

/**
 * TodoListCardContent Component
 * 
 * Renders todo list content for the floating card.
 * Displays all todo items with their status in a compact format.
 * 
 * @param {Object} props
 * @param {Array} props.todos - Array of todo items
 * @param {number} props.total - Total number of todos
 * @param {number} props.completed - Number of completed todos
 * @param {number} props.in_progress - Number of in-progress todos
 * @param {number} props.pending - Number of pending todos
 */
function TodoListCardContent({ todos, total, completed, in_progress, pending }) {
  if (!todos || todos.length === 0) {
    return (
      <div className="text-sm" style={{ color: '#FFFFFF', opacity: 0.7 }}>
        No todos yet
      </div>
    );
  }

  /**
   * Get icon for todo item based on status
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
   * Get status label
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
    <div className="space-y-3">
      {/* Header with icon and summary */}
      <div className="flex items-center gap-2 pb-2" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <ListTodo className="h-4 w-4" style={{ color: '#6155F5' }} />
        <span className="text-sm font-semibold" style={{ color: '#FFFFFF' }}>
          Todo List
        </span>
        <span className="text-xs ml-auto" style={{ color: '#FFFFFF', opacity: 0.6 }}>
          {completed}/{total} completed
        </span>
      </div>

      {/* Status summary */}
      <div className="flex items-center gap-3 text-xs" style={{ color: '#FFFFFF', opacity: 0.7 }}>
        <div>
          <span className="font-semibold">Total:</span> {total}
        </div>
        <div style={{ color: '#0FEDBE' }}>
          <span className="font-semibold">Completed:</span> {completed}
        </div>
        <div style={{ color: '#6155F5' }}>
          <span className="font-semibold">In Progress:</span> {in_progress}
        </div>
        <div>
          <span className="font-semibold">Pending:</span> {pending}
        </div>
      </div>

      {/* Todo items list */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {todos.map((todo, index) => (
          <div
            key={`todo-${index}-${todo.activeForm || index}`}
            className="flex items-start gap-2 p-2 rounded-md"
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
                <span className="text-sm font-medium" style={{ color: '#FFFFFF', opacity: 0.9 }}>
                  {todo.activeForm || `Task ${index + 1}`}
                </span>
                {/* Status badge */}
                <span
                  className="text-xs px-1.5 py-0.5 rounded-full"
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
  );
}

export default TodoListCardContent;
