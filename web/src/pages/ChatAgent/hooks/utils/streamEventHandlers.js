/**
 * Streaming event handlers for live message streaming
 * Handles events from the SSE stream during active message sending
 */

/**
 * Extracts the last markdown bold title (**...**) from reasoning content for the icon label.
 * Used only during live streaming; history always shows "Reasoning".
 * @param {string} content - Accumulated reasoning text
 * @returns {string|null} Last **title** inner text or null
 */
function extractLastReasoningTitle(content) {
  if (!content || typeof content !== 'string') return null;
  const matches = content.matchAll(/\*\*([^*]+)\*\*/g);
  let last = null;
  for (const m of matches) last = m[1].trim();
  return last || null;
}

/**
 * Initializes per-task ref state if it doesn't exist yet.
 * Shared by all subagent event handlers to avoid repeated boilerplate.
 * @param {Object} refs - Refs object with subagentStateRefs
 * @param {string} taskId - Task ID (e.g., "task:k7Xm2p")
 * @returns {Object} The task refs ({ contentOrderCounterRef, currentReasoningIdRef, currentToolCallIdRef, messages })
 */
export function getOrCreateTaskRefs(refs, taskId) {
  const subagentStateRefs = refs.subagentStateRefs || {};
  if (!subagentStateRefs[taskId]) {
    subagentStateRefs[taskId] = {
      contentOrderCounterRef: { current: 0 },
      currentReasoningIdRef: { current: null },
      currentToolCallIdRef: { current: null },
      messages: [],
      runIndex: 0,
    };
  }
  return subagentStateRefs[taskId];
}

/**
 * Handles reasoning signal events during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.signalContent - Signal content ('start' or 'complete')
 * @param {Object} params.refs - Refs object with contentOrderCounterRef, currentReasoningIdRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleReasoningSignal({ assistantMessageId, signalContent, refs, setMessages }) {
  const { contentOrderCounterRef, currentReasoningIdRef } = refs;

  if (signalContent === 'start') {
    // Reasoning process has started - create new reasoning process
    const reasoningId = `reasoning-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    currentReasoningIdRef.current = reasoningId;
    contentOrderCounterRef.current++;
    const currentOrder = contentOrderCounterRef.current;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== assistantMessageId) return msg;

        const newSegments = [
          ...(msg.contentSegments || []),
          {
            type: 'reasoning',
            reasoningId,
            order: currentOrder,
          },
        ];

        const newReasoningProcesses = {
          ...(msg.reasoningProcesses || {}),
          [reasoningId]: {
            content: '',
            isReasoning: true,
            reasoningComplete: false,
            order: currentOrder,
          },
        };

        return {
          ...msg,
          contentSegments: newSegments,
          reasoningProcesses: newReasoningProcesses,
        };
      })
    );
    return true;
  } else if (signalContent === 'complete') {
    // Reasoning process has completed - clear title so icon shows "Reasoning"
    if (currentReasoningIdRef.current) {
      const reasoningId = currentReasoningIdRef.current;
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== assistantMessageId) return msg;

          const reasoningProcesses = { ...(msg.reasoningProcesses || {}) };
          if (reasoningProcesses[reasoningId]) {
            reasoningProcesses[reasoningId] = {
              ...reasoningProcesses[reasoningId],
              isReasoning: false,
              reasoningComplete: true,
              reasoningTitle: null,
              _completedAt: refs.isReconnect ? 0 : Date.now(),
            };
          }

          return {
            ...msg,
            reasoningProcesses,
          };
        })
      );
      currentReasoningIdRef.current = null;
    }
    return true;
  }
  return false;
}

/**
 * Handles reasoning content chunks during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.content - Reasoning content chunk
 * @param {Object} params.refs - Refs object with currentReasoningIdRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleReasoningContent({ assistantMessageId, content, refs, setMessages }) {
  const { currentReasoningIdRef } = refs;

  if (currentReasoningIdRef.current && content) {
    const reasoningId = currentReasoningIdRef.current;
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== assistantMessageId) return msg;

        const reasoningProcesses = { ...(msg.reasoningProcesses || {}) };
        if (reasoningProcesses[reasoningId]) {
          const newContent = (reasoningProcesses[reasoningId].content || '') + content;
          const reasoningTitle = extractLastReasoningTitle(newContent) ?? reasoningProcesses[reasoningId].reasoningTitle ?? null;
          reasoningProcesses[reasoningId] = {
            ...reasoningProcesses[reasoningId],
            content: newContent,
            isReasoning: true,
            reasoningTitle,
          };
        }

        return {
          ...msg,
          reasoningProcesses,
        };
      })
    );
    return true;
  }
  return false;
}

/**
 * Handles text content chunks during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.content - Text content chunk
 * @param {string} params.finishReason - Optional finish reason
 * @param {Object} params.refs - Refs object with contentOrderCounterRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleTextContent({ assistantMessageId, content, finishReason, refs, setMessages }) {
  const { contentOrderCounterRef } = refs;

  // Handle finish_reason
  if (finishReason) {
    if (finishReason === 'tool_calls' && !content) {
      // Message is requesting tool calls, don't mark as complete yet
      return false; // Let tool_calls handler process this
    } else if (!content) {
      // Metadata chunk with finish_reason but no content
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
      return true;
    }
    // If finish_reason exists but content also exists, continue to process content
  }

  // Process text content chunks
  if (content) {
    contentOrderCounterRef.current++;
    const currentOrder = contentOrderCounterRef.current;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== assistantMessageId) return msg;

        const newSegments = [
          ...(msg.contentSegments || []),
          {
            type: 'text',
            content,
            order: currentOrder,
          },
        ];

        const accumulatedText = (msg.content || '') + content;

        return {
          ...msg,
          contentSegments: newSegments,
          content: accumulatedText,
          contentType: 'text',
          isStreaming: true,
        };
      })
    );
    return true;
  } else if (finishReason) {
    // Message is complete (finish_reason present with no content means end of stream)
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantMessageId
          ? { ...msg, isStreaming: false }
          : msg
      )
    );
    return true;
  }
  return false;
}

/**
 * Handles tool_calls events during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {Array} params.toolCalls - Array of tool call objects
 * @param {string} params.finishReason - Optional finish reason
 * @param {Object} params.refs - Refs object with contentOrderCounterRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleToolCalls({ assistantMessageId, toolCalls, finishReason, refs, setMessages }) {
  const { contentOrderCounterRef } = refs;

  if (!toolCalls || !Array.isArray(toolCalls)) {
    return false;
  }

  // Track creation times outside React state so handleToolCallResult can read them synchronously
  if (!refs._toolCreatedAt) refs._toolCreatedAt = {};

  toolCalls.forEach((toolCall) => {
    const toolCallId = toolCall.id;

    if (toolCallId) {
      if (!refs.isReconnect && !refs._toolCreatedAt[toolCallId]) {
        refs._toolCreatedAt[toolCallId] = Date.now();
      }
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== assistantMessageId) return msg;

          const toolCallProcesses = { ...(msg.toolCallProcesses || {}) };
          const contentSegments = [...(msg.contentSegments || [])];

          if (!toolCallProcesses[toolCallId]) {
            contentOrderCounterRef.current++;
            const currentOrder = contentOrderCounterRef.current;

            contentSegments.push({
              type: 'tool_call',
              toolCallId,
              order: currentOrder,
            });

            toolCallProcesses[toolCallId] = {
              toolName: toolCall.name,
              toolCall: toolCall,
              toolCallResult: null,
              isInProgress: true,
              isComplete: false,
              _createdAt: refs.isReconnect ? 0 : Date.now(),
              order: currentOrder,
            };
          } else {
            toolCallProcesses[toolCallId] = {
              ...toolCallProcesses[toolCallId],
              toolName: toolCall.name,
              toolCall: toolCall,
              isInProgress: true,
            };
          }

          // If this tool is the Task tool (subagent spawner), also create a subagent_task segment
          // Mirrors historyEventHandlers.js logic for consistency
          const subagentTasks = { ...(msg.subagentTasks || {}) };
          const isTaskTool = toolCall.name === 'task' || toolCall.name === 'Task';
          const isNewSpawn = !toolCall.args?.task_id;
          if (isTaskTool && toolCallId && isNewSpawn) {
            const subagentId = toolCallId;
            const hasExistingSubagentSegment = contentSegments.some(
              (s) => s.type === 'subagent_task' && s.subagentId === subagentId
            );

            if (!hasExistingSubagentSegment) {
              contentSegments.push({
                type: 'subagent_task',
                subagentId,
                order: contentOrderCounterRef.current,
              });
            }

            subagentTasks[subagentId] = {
              ...(subagentTasks[subagentId] || {}),
              subagentId,
              description: toolCall.args?.description || '',
              type: toolCall.args?.subagent_type || 'general-purpose',
              status: 'running',
            };
          } else if (isTaskTool && toolCallId && !isNewSpawn) {
            // Resume/follow-up call — show a new card with "resumed" indicator
            // Normalize to "task:xxx" format to match floating card keys
            const rawTargetId = toolCall.args?.task_id || '';
            const resumeTargetId = rawTargetId.startsWith('task:') ? rawTargetId : `task:${rawTargetId}`;
            contentSegments.push({
              type: 'subagent_task',
              subagentId: toolCallId,
              resumeTargetId,
              order: contentOrderCounterRef.current,
            });
            subagentTasks[toolCallId] = {
              subagentId: toolCallId,
              resumeTargetId,
              description: toolCall.args?.description || '',
              type: toolCall.args?.subagent_type || 'general-purpose',
              status: 'running',
              resumed: true,
            };
          }

          return {
            ...msg,
            contentSegments,
            toolCallProcesses,
            subagentTasks,
            pendingToolCallChunks: {},
          };
        })
      );
    }
  });

  return true;
}

/**
 * Handles tool_call_result events during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.toolCallId - ID of the tool call
 * @param {Object} params.result - Tool call result object
 * @param {Object} params.refs - Refs object with contentOrderCounterRef, currentToolCallIdRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleToolCallResult({ assistantMessageId, toolCallId, result, refs, setMessages }) {
  const { contentOrderCounterRef, currentToolCallIdRef } = refs;

  if (!toolCallId) {
    return false;
  }

  setMessages((prev) =>
    prev.map((msg) => {
      if (msg.id !== assistantMessageId) return msg;

      const toolCallProcesses = { ...(msg.toolCallProcesses || {}) };

      // Tool call failed only if content starts with "ERROR" (backend convention)
      const resultContent = result.content || '';
      const isFailed = typeof resultContent === 'string' && resultContent.trim().startsWith('ERROR');

      // Track subagent task status updates
      const subagentTasks = { ...(msg.subagentTasks || {}) };

      if (toolCallProcesses[toolCallId]) {
        toolCallProcesses[toolCallId] = {
          ...toolCallProcesses[toolCallId],
          toolCallResult: {
            content: result.content,
            content_type: result.content_type,
            tool_call_id: result.tool_call_id,
            artifact: result.artifact,
          },
          isInProgress: false,
          isComplete: true,
          isFailed,
        };
      } else {
        // Orphaned tool_call_result without matching tool_calls (e.g., SubmitPlan
        // result arriving in a HITL resume stream). Skip silently.
        return msg;
      }

      // If this toolCallId is associated with a subagent task, store the tool call result
      // but do NOT mark as 'completed' — the Task tool returns immediately ("Task-N started
      // in background") while the actual subagent is still running. Real completion comes
      // via the per-task SSE stream closing.
      // Also propagate description from artifact if the inline card's description is empty.
      if (subagentTasks[toolCallId]) {
        const artifactDescription = result.artifact?.description;
        const existingDescription = subagentTasks[toolCallId].description;
        subagentTasks[toolCallId] = {
          ...subagentTasks[toolCallId],
          toolCallResult: result.content,
          ...(artifactDescription && !existingDescription ? { description: artifactDescription } : {}),
        };
      }

      return { ...msg, toolCallProcesses, subagentTasks };
    })
  );

  // Reset current tool call ID after result is received
  if (currentToolCallIdRef.current === toolCallId) {
    currentToolCallIdRef.current = null;
  }

  return true;
}

/**
 * Handles artifact events with artifact_type: "todo_update" during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.artifactType - Type of artifact ("todo_update")
 * @param {string} params.artifactId - ID of the artifact
 * @param {Object} params.payload - Payload containing todos array and status counts
 * @param {Object} params.refs - Refs object with contentOrderCounterRef
 * @param {Function} params.setMessages - State setter for messages
 * @returns {boolean} True if event was handled
 */
export function handleTodoUpdate({ assistantMessageId, artifactType, artifactId, payload, refs, setMessages }) {
  const { contentOrderCounterRef, updateTodoListCard, isNewConversation } = refs;

  if (process.env.NODE_ENV === 'development') {
    console.log('[handleTodoUpdate] Called with:', { assistantMessageId, artifactType, artifactId, payload, isNewConversation });
  }

  // Only handle todo_update artifacts
  if (artifactType !== 'todo_update' || !payload) {
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleTodoUpdate] Skipping - artifactType:', artifactType, 'hasPayload:', !!payload);
    }
    return false;
  }

  const { todos, total, completed, in_progress, pending } = payload;
  if (process.env.NODE_ENV === 'development') {
    console.log('[handleTodoUpdate] Extracted data:', { todos, total, completed, in_progress, pending });
  }

  // Update floating card with todo list data (only during live streaming, not history)
  // Do this before setMessages to ensure we have the latest data
  // Always update the card if updateTodoListCard is available, even if todos array is empty
  // This ensures the card persists and shows the latest state
  if (updateTodoListCard) {
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleTodoUpdate] Updating todo list card, isNewConversation:', isNewConversation, 'todos count:', todos?.length || 0);
    }
    updateTodoListCard(
      {
        todos: todos || [],
        total: total || 0,
        completed: completed || 0,
        in_progress: in_progress || 0,
        pending: pending || 0,
      },
      isNewConversation || false
    );
  }

  // Use artifactId as the base todoListId to track updates to the same logical todo list
  // But create a unique segmentId for each event to preserve chronological order
  const baseTodoListId = artifactId || `todo-list-base-${Date.now()}`;
  // Create a unique segment ID that includes timestamp to ensure chronological ordering
  const segmentId = `${baseTodoListId}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  if (process.env.NODE_ENV === 'development') {
    console.log('[handleTodoUpdate] Using baseTodoListId:', baseTodoListId, 'segmentId:', segmentId);
  }

  setMessages((prev) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleTodoUpdate] Current messages:', prev.map(m => ({ id: m.id, role: m.role, hasSegments: !!m.contentSegments, hasTodoProcesses: !!m.todoListProcesses })));
    }
    const updated = prev.map((msg) => {
      if (msg.id !== assistantMessageId) return msg;

      if (process.env.NODE_ENV === 'development') {
        console.log('[handleTodoUpdate] Found matching message:', msg.id);
      }
      const todoListProcesses = { ...(msg.todoListProcesses || {}) };
      const contentSegments = [...(msg.contentSegments || [])];

      // Always create a new segment for each todo_update event to preserve chronological order
      // Increment order counter to get the current position in the stream
      contentOrderCounterRef.current++;
      const currentOrder = contentOrderCounterRef.current;
      if (process.env.NODE_ENV === 'development') {
        console.log('[handleTodoUpdate] Creating new todo list segment with order:', currentOrder, 'segmentId:', segmentId);
      }

      // Add new segment at the current chronological position
      contentSegments.push({
        type: 'todo_list',
        todoListId: segmentId, // Use unique segmentId for this specific event
        order: currentOrder,
      });

      // Store the todo list data with the segmentId
      // If this is an update to an existing logical todo list (same artifactId),
      // we still create a new segment but can reference the base ID for data updates
      todoListProcesses[segmentId] = {
        todos: todos || [],
        total: total || 0,
        completed: completed || 0,
        in_progress: in_progress || 0,
        pending: pending || 0,
        order: currentOrder,
        baseTodoListId: baseTodoListId, // Keep reference to base ID for potential future use
      };
      if (process.env.NODE_ENV === 'development') {
        console.log('[handleTodoUpdate] Created new todo list process:', todoListProcesses[segmentId]);
      }

      const updatedMsg = {
        ...msg,
        contentSegments,
        todoListProcesses,
      };
      if (process.env.NODE_ENV === 'development') {
        console.log('[handleTodoUpdate] Updated message:', {
          id: updatedMsg.id,
          segmentsCount: updatedMsg.contentSegments?.length,
          todoListIds: Object.keys(updatedMsg.todoListProcesses || {})
        });
      }
      return updatedMsg;
    });
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleTodoUpdate] Final messages after update:', updated.map(m => ({ id: m.id, segmentsCount: m.contentSegments?.length, todoListIds: Object.keys(m.todoListProcesses || {}) })));
    }
    return updated;
  });

  return true;
}

/**
 * Handles tool_call_chunks events during streaming.
 * Tracks pending tool call chunks so the UI can show a "preparing" indicator
 * while the LLM is still generating tool call arguments.
 * @param {Object} params - Handler parameters
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {Array} params.chunks - Array of tool_call_chunk objects
 * @param {Function} params.setMessages - State setter for messages
 */
export function handleToolCallChunks({ assistantMessageId, chunks, setMessages }) {
  if (!chunks || !Array.isArray(chunks)) return;

  chunks.forEach((chunk) => {
    const key = `${chunk.index ?? 0}`;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== assistantMessageId) return msg;
        const pending = { ...(msg.pendingToolCallChunks || {}) };
        const existing = pending[key] || { toolName: null, chunkCount: 0, argsLength: 0, firstSeenAt: Date.now() };

        pending[key] = {
          toolName: chunk.name || existing.toolName,
          chunkCount: existing.chunkCount + 1,
          argsLength: existing.argsLength + (chunk.args?.length || 0),
          firstSeenAt: existing.firstSeenAt,
        };

        return { ...msg, pendingToolCallChunks: pending };
      })
    );
  });
}

/**
 * Checks if an event is from a subagent.
 * Backend convention:
 * - Main agent: agent.startsWith("model:")
 * - Tool node: agent === "tools"
 * - Subagent: agent contains ":" but does NOT start with "model:" and is NOT "tools"
 * Subagent format: agent_id = "{subagent_type}:{uuid4}" (e.g., "research:550e8400-...")
 * @param {Object} event - Event object
 * @returns {boolean} True if event is from subagent
 */
export function isSubagentEvent(event) {
  const agent = event?.agent;
  if (!agent || typeof agent !== 'string') {
    return false;
  }
  return agent.startsWith('task:');
}

/**
 * Handles subagent message chunks during streaming
 * Similar to main agent handlers but for subagent events
 * @param {Object} params - Handler parameters
 * @param {string} params.taskId - Task ID (e.g., "Task-1")
 * @param {string} params.assistantMessageId - ID of the assistant message being updated
 * @param {string} params.contentType - Content type (reasoning_signal, reasoning, text)
 * @param {string} params.content - Content chunk
 * @param {string} params.finishReason - Optional finish reason
 * @param {Object} params.refs - Refs object with subagent state refs
 * @param {Function} params.updateSubagentCard - Callback to update subagent card
 * @returns {boolean} True if event was handled
 */
export function handleSubagentMessageChunk({ 
  taskId, 
  assistantMessageId, 
  contentType, 
  content, 
  finishReason,
  refs,
  updateSubagentCard 
}) {
  if (!taskId || !assistantMessageId || !updateSubagentCard) {
    return false;
  }

  const taskRefs = getOrCreateTaskRefs(refs, taskId);
  const { contentOrderCounterRef, currentReasoningIdRef } = taskRefs;

  // Handle finishReason with no content — model call complete
  if (finishReason && !content && contentType !== 'reasoning_signal') {
    if (finishReason === 'tool_calls') {
      return false; // More work coming, let tool_calls handler process
    }
    // finish_reason: "stop" — subagent's model call is done
    const updatedMessages = [...taskRefs.messages];
    const msgIdx = updatedMessages.findIndex(m => m.id === assistantMessageId);
    if (msgIdx !== -1) {
      updatedMessages[msgIdx] = { ...updatedMessages[msgIdx], isStreaming: false };
      taskRefs.messages = updatedMessages;
      updateSubagentCard(taskId, { messages: updatedMessages });
    }
    return true;
  }

  // Handle reasoning_signal
  if (contentType === 'reasoning_signal') {
    const signalContent = content || '';
    if (signalContent === 'start') {
      const reasoningId = `reasoning-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      currentReasoningIdRef.current = reasoningId;
      contentOrderCounterRef.current++;
      const currentOrder = contentOrderCounterRef.current;

      // Update subagent message
      const updatedMessages = [...taskRefs.messages];
      let messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
      
      if (messageIndex === -1) {
        // Create new message
        updatedMessages.push({
          id: assistantMessageId,
          role: 'assistant',
          contentSegments: [],
          reasoningProcesses: {},
          toolCallProcesses: {},
          isStreaming: true,
        });
        messageIndex = updatedMessages.length - 1;
      }

      const msg = updatedMessages[messageIndex];
      msg.contentSegments = [
        ...(msg.contentSegments || []),
        {
          type: 'reasoning',
          reasoningId,
          order: currentOrder,
        },
      ];
      msg.reasoningProcesses = {
        ...(msg.reasoningProcesses || {}),
        [reasoningId]: {
          content: '',
          isReasoning: true,
          reasoningComplete: false,
          order: currentOrder,
        },
      };

      taskRefs.messages = updatedMessages;
      // Update card with messages only - don't update status here
      // Status is managed by per-task stream close to prevent overwriting 'completed' status
      updateSubagentCard(taskId, {
        messages: updatedMessages,
      });
      return true;
    } else if (signalContent === 'complete') {
      if (currentReasoningIdRef.current) {
        const reasoningId = currentReasoningIdRef.current;
        const updatedMessages = [...taskRefs.messages];
        const messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
        
        if (messageIndex !== -1) {
          const msg = updatedMessages[messageIndex];
          const reasoningProcesses = { ...(msg.reasoningProcesses || {}) };
          if (reasoningProcesses[reasoningId]) {
            reasoningProcesses[reasoningId] = {
              ...reasoningProcesses[reasoningId],
              isReasoning: false,
              reasoningComplete: true,
              reasoningTitle: null,
              _completedAt: refs.isReconnect ? 0 : Date.now(),
            };
          }
          msg.reasoningProcesses = reasoningProcesses;
          taskRefs.messages = updatedMessages;
          updateSubagentCard(taskId, { messages: updatedMessages });
        }
        currentReasoningIdRef.current = null;
      }
      return true;
    }
  }

  // Handle reasoning content
  if (contentType === 'reasoning' && content && currentReasoningIdRef.current) {
    const reasoningId = currentReasoningIdRef.current;
    const updatedMessages = [...taskRefs.messages];
    let messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
    
    // Create message if it doesn't exist (edge case: reasoning content arrives before start signal)
    if (messageIndex === -1) {
      updatedMessages.push({
        id: assistantMessageId,
        role: 'assistant',
        contentSegments: [],
        reasoningProcesses: {},
        toolCallProcesses: {},
        isStreaming: true,
      });
      messageIndex = updatedMessages.length - 1;
    }

    const msg = updatedMessages[messageIndex];
    const reasoningProcesses = { ...(msg.reasoningProcesses || {}) };

    // Create reasoning process if it doesn't exist (edge case: reasoning content arrives before start signal)
    if (!reasoningProcesses[reasoningId]) {
      // Need to add the reasoning segment to contentSegments as well
      contentOrderCounterRef.current++;
      const currentOrder = contentOrderCounterRef.current;
      
      msg.contentSegments = [
        ...(msg.contentSegments || []),
        {
          type: 'reasoning',
          reasoningId,
          order: currentOrder,
        },
      ];
      
      reasoningProcesses[reasoningId] = {
        content: '',
        isReasoning: true,
        reasoningComplete: false,
        order: currentOrder,
      };
    }
    
    // Update reasoning content - accumulate the content
    const existingContent = reasoningProcesses[reasoningId]?.content || '';
    const newContent = existingContent + content;
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[handleSubagentMessageChunk] Updating reasoning content:', {
        taskId,
        reasoningId,
        existingContentLength: existingContent.length,
        newChunkLength: content.length,
        newContentLength: newContent.length,
      });
    }
    
    const reasoningTitle = extractLastReasoningTitle(newContent) ?? reasoningProcesses[reasoningId].reasoningTitle ?? null;
    reasoningProcesses[reasoningId] = {
      ...reasoningProcesses[reasoningId],
      content: newContent,
      isReasoning: true,
      reasoningTitle,
    };
    
    msg.reasoningProcesses = reasoningProcesses;
    taskRefs.messages = updatedMessages;
    updateSubagentCard(taskId, { messages: updatedMessages });
    return true;
  }

  // Handle text content
  if (contentType === 'text' && content) {
    contentOrderCounterRef.current++;
    const currentOrder = contentOrderCounterRef.current;

    const updatedMessages = [...taskRefs.messages];
    let messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
    
    if (messageIndex === -1) {
      updatedMessages.push({
        id: assistantMessageId,
        role: 'assistant',
        contentSegments: [],
        reasoningProcesses: {},
        toolCallProcesses: {},
        content: '',
        isStreaming: true,
      });
      messageIndex = updatedMessages.length - 1;
    }

    const msg = updatedMessages[messageIndex];
    msg.contentSegments = [
      ...(msg.contentSegments || []),
      {
        type: 'text',
        content,
        order: currentOrder,
      },
    ];
    msg.content = (msg.content || '') + content;
    msg.contentType = 'text';
    msg.isStreaming = true;

    taskRefs.messages = updatedMessages;
    updateSubagentCard(taskId, { messages: updatedMessages });
    return true;
  }

  return false;
}

/**
 * Handles subagent tool_call_chunks events during streaming.
 * Updates pendingToolCallChunks on the subagent assistant message to show
 * a "preparing" indicator while the LLM streams tool arguments.
 * @param {Object} params - Handler parameters
 * @param {string} params.taskId - Task ID
 * @param {string} params.assistantMessageId - ID of the assistant message
 * @param {Array} params.chunks - Array of tool call chunk objects
 * @param {Object} params.refs - Refs object with subagent state refs
 * @param {Function} params.updateSubagentCard - Callback to update subagent card
 * @returns {boolean} True if event was handled
 */
export function handleSubagentToolCallChunks({ taskId, assistantMessageId, chunks, refs, updateSubagentCard }) {
  if (!taskId || !assistantMessageId || !chunks || !Array.isArray(chunks) || !updateSubagentCard) {
    return false;
  }

  const taskRefs = getOrCreateTaskRefs(refs, taskId);
  const updatedMessages = [...taskRefs.messages];

  let messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
  if (messageIndex === -1) {
    updatedMessages.push({
      id: assistantMessageId,
      role: 'assistant',
      contentSegments: [],
      reasoningProcesses: {},
      toolCallProcesses: {},
      pendingToolCallChunks: {},
      isStreaming: true,
    });
    messageIndex = updatedMessages.length - 1;
  }

  const msg = { ...updatedMessages[messageIndex] };
  const pending = { ...(msg.pendingToolCallChunks || {}) };

  chunks.forEach((chunk) => {
    const key = `${chunk.index ?? 0}`;
    const existing = pending[key] || { toolName: null, chunkCount: 0, argsLength: 0, firstSeenAt: Date.now() };
    pending[key] = {
      toolName: chunk.name || existing.toolName,
      chunkCount: existing.chunkCount + 1,
      argsLength: existing.argsLength + (chunk.args?.length || 0),
      firstSeenAt: existing.firstSeenAt,
    };
  });

  msg.pendingToolCallChunks = pending;
  updatedMessages[messageIndex] = msg;
  taskRefs.messages = updatedMessages;

  updateSubagentCard(taskId, { messages: taskRefs.messages });
  return true;
}

/**
 * Handles subagent tool_calls events during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.taskId - Task ID
 * @param {string} params.assistantMessageId - ID of the assistant message
 * @param {Array} params.toolCalls - Array of tool call objects
 * @param {Object} params.refs - Refs object with subagent state refs
 * @param {Function} params.updateSubagentCard - Callback to update subagent card
 * @returns {boolean} True if event was handled
 */
export function handleSubagentToolCalls({ taskId, assistantMessageId, toolCalls, refs, updateSubagentCard }) {
  if (!taskId || !assistantMessageId || !toolCalls || !Array.isArray(toolCalls) || !updateSubagentCard) {
    return false;
  }

  const taskRefs = getOrCreateTaskRefs(refs, taskId);
  const { contentOrderCounterRef } = taskRefs;

  if (process.env.NODE_ENV === 'development') {
    console.log('[handleSubagentToolCalls] Processing tool calls:', {
      taskId,
      assistantMessageId,
      toolCallsCount: toolCalls.length,
      toolCallIds: toolCalls.map(tc => tc.id),
    });
  }

  toolCalls.forEach((toolCall) => {
    const toolCallId = toolCall.id;
    if (toolCallId) {
      const updatedMessages = [...taskRefs.messages];
      let messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
      
      if (messageIndex === -1) {
        updatedMessages.push({
          id: assistantMessageId,
          role: 'assistant',
          contentSegments: [],
          reasoningProcesses: {},
          toolCallProcesses: {},
          isStreaming: true,
        });
        messageIndex = updatedMessages.length - 1;
      }

      const msg = updatedMessages[messageIndex];
      const toolCallProcesses = { ...(msg.toolCallProcesses || {}) };
      const contentSegments = [...(msg.contentSegments || [])];

      if (!toolCallProcesses[toolCallId]) {
        contentOrderCounterRef.current++;
        const currentOrder = contentOrderCounterRef.current;

        contentSegments.push({
          type: 'tool_call',
          toolCallId,
          order: currentOrder,
        });

        toolCallProcesses[toolCallId] = {
          toolName: toolCall.name,
          toolCall: toolCall,
          toolCallResult: null,
          isInProgress: true,
          isComplete: false,
          order: currentOrder,
        };
        
        if (process.env.NODE_ENV === 'development') {
          console.log('[handleSubagentToolCalls] Created new tool call:', {
            taskId,
            assistantMessageId,
            toolCallId,
            toolName: toolCall.name,
            order: currentOrder,
          });
        }
      } else {
        toolCallProcesses[toolCallId] = {
          ...toolCallProcesses[toolCallId],
          toolName: toolCall.name,
          toolCall: toolCall,
          isInProgress: true,
        };
      }

      msg.contentSegments = contentSegments;
      msg.toolCallProcesses = toolCallProcesses;
      // Clear pending chunks now that the final tool_calls event has arrived
      msg.pendingToolCallChunks = {};
      taskRefs.messages = updatedMessages;
    }
  });

  // Update subagent card: set currentTool to the first tool being called
  // This ensures the status shows which tool is currently running
  const firstToolCall = toolCalls.length > 0 ? toolCalls[0] : null;
  const currentToolName = firstToolCall?.name || '';

  updateSubagentCard(taskId, {
    messages: taskRefs.messages,
    currentTool: currentToolName, // Update current tool to show what's running
  });
  return true;
}

/**
 * Handles subagent tool_call_result events during streaming
 * @param {Object} params - Handler parameters
 * @param {string} params.taskId - Task ID
 * @param {string} params.assistantMessageId - ID of the assistant message
 * @param {string} params.toolCallId - ID of the tool call
 * @param {Object} params.result - Tool call result object
 * @param {Object} params.refs - Refs object with subagent state refs
 * @param {Function} params.updateSubagentCard - Callback to update subagent card
 * @returns {boolean} True if event was handled
 */
export function handleSubagentToolCallResult({ taskId, assistantMessageId, toolCallId, result, refs, updateSubagentCard }) {
  if (!taskId || !toolCallId || !updateSubagentCard) {
    return false;
  }

  const taskRefs = getOrCreateTaskRefs(refs, taskId);
  const { contentOrderCounterRef } = taskRefs;

  const updatedMessages = [...taskRefs.messages];
  
  // Find the message that contains this tool call
  // tool_call_result events have a different event.id than tool_calls events,
  // so we need to search by tool_call_id instead of message ID
  let messageIndex = -1;
  let targetMessage = null;
  
  if (process.env.NODE_ENV === 'development') {
    console.log('[handleSubagentToolCallResult] Searching for tool call:', {
      taskId,
      toolCallId,
      assistantMessageId,
      existingMessages: updatedMessages.map(m => ({
        id: m.id,
        toolCallIds: Object.keys(m.toolCallProcesses || {}),
      })),
    });
  }
  
  // First, try to find message by assistantMessageId (if provided and matches)
  if (assistantMessageId) {
    messageIndex = updatedMessages.findIndex(m => m.id === assistantMessageId);
    if (messageIndex !== -1) {
      targetMessage = updatedMessages[messageIndex];
      // Verify this message actually has the tool call
      if (!targetMessage.toolCallProcesses?.[toolCallId]) {
        if (process.env.NODE_ENV === 'development') {
          console.warn('[handleSubagentToolCallResult] Message found but tool call not in it:', {
            messageId: assistantMessageId,
            toolCallId,
            availableToolCalls: Object.keys(targetMessage.toolCallProcesses || {}),
          });
        }
        messageIndex = -1;
        targetMessage = null;
      }
    }
  }
  
  // If not found by message ID, search for message containing this tool call
  if (messageIndex === -1) {
    for (let i = 0; i < updatedMessages.length; i++) {
      const msg = updatedMessages[i];
      if (msg.toolCallProcesses?.[toolCallId]) {
        messageIndex = i;
        targetMessage = msg;
        if (process.env.NODE_ENV === 'development') {
          console.log('[handleSubagentToolCallResult] Found message by tool call ID:', {
            messageId: msg.id,
            toolCallId,
          });
        }
        break;
      }
    }
  }
  
  if (messageIndex === -1) {
    // Tool call doesn't exist yet - create new message with tool call result
    // This can happen if tool_call_result arrives before tool_calls
    contentOrderCounterRef.current++;
    const currentOrder = contentOrderCounterRef.current;
    
    updatedMessages.push({
      id: assistantMessageId || `subagent-msg-${Date.now()}`,
      role: 'assistant',
      contentSegments: [{
        type: 'tool_call',
        toolCallId,
        order: currentOrder,
      }],
      reasoningProcesses: {},
      toolCallProcesses: {
        [toolCallId]: {
          toolName: 'Unknown Tool',
          toolCall: null,
          toolCallResult: {
            content: result.content,
            content_type: result.content_type,
            tool_call_id: result.tool_call_id,
            artifact: result.artifact,
          },
          isInProgress: false,
          isComplete: true,
          isFailed: typeof result.content === 'string' && (result.content || '').trim().startsWith('ERROR'),
          order: currentOrder,
        },
      },
    });
    
    if (process.env.NODE_ENV === 'development') {
      console.warn('[handleSubagentToolCallResult] Tool call not found, created new message:', {
        taskId,
        toolCallId,
        assistantMessageId,
      });
    }
  } else {
    // Update existing tool call with result
    const msg = updatedMessages[messageIndex];
    const toolCallProcesses = { ...(msg.toolCallProcesses || {}) };
    
    // Tool call failed only if content starts with "ERROR"
    const resultContent = result.content || '';
    const isFailed = typeof resultContent === 'string' && resultContent.trim().startsWith('ERROR');
    
    if (toolCallProcesses[toolCallId]) {
      toolCallProcesses[toolCallId] = {
        ...toolCallProcesses[toolCallId],
        toolCallResult: {
          content: result.content,
          content_type: result.content_type,
          tool_call_id: result.tool_call_id,
          artifact: result.artifact,
        },
        isInProgress: false,
        isComplete: true,
        isFailed,
      };
    } else {
      // Edge case: message exists but tool call doesn't - add it
      contentOrderCounterRef.current++;
      const currentOrder = contentOrderCounterRef.current;

      const contentSegments = [...(msg.contentSegments || [])];
      contentSegments.push({
        type: 'tool_call',
        toolCallId,
        order: currentOrder,
      });

      toolCallProcesses[toolCallId] = {
        toolName: 'Unknown Tool',
        toolCall: null,
        toolCallResult: {
          content: result.content,
          content_type: result.content_type,
          tool_call_id: result.tool_call_id,
          artifact: result.artifact,
        },
        isInProgress: false,
        isComplete: true,
        isFailed,
        order: currentOrder,
      };

      msg.contentSegments = contentSegments;
    }
    
    msg.toolCallProcesses = toolCallProcesses;
  }

  taskRefs.messages = updatedMessages;
  
  // Detect if the tool call that just completed was a failure
  // We need to check the tool call process that was just updated
  let justCompletedToolFailed = false;
  let justCompletedToolName = '';
  
  // Find the tool call that just completed (it should be in updatedMessages now)
  for (const msg of updatedMessages) {
    const toolCallProcesses = msg.toolCallProcesses || {};
    const completedToolCall = toolCallProcesses[toolCallId];
    if (completedToolCall && completedToolCall.isComplete) {
      // This is the tool call that just completed
      justCompletedToolFailed = completedToolCall.isFailed || false;
      justCompletedToolName = completedToolCall.toolName || '';
      break;
    }
  }
  
  // Update subagent card: clear currentTool when tool call completes
  // Priority:
  // 1. If the tool that just completed failed, clear currentTool immediately
  // 2. Otherwise, check if there are any other in-progress tool calls
  let hasInProgressTool = false;
  let currentToolName = '';
  
  if (!justCompletedToolFailed) {
    // Only check for in-progress tools if the completed tool didn't fail
    // If it failed, we want to clear currentTool immediately
    for (const msg of updatedMessages) {
      const toolCallProcesses = msg.toolCallProcesses || {};
      for (const [tcId, tcProcess] of Object.entries(toolCallProcesses)) {
        if (tcProcess.isInProgress && !tcProcess.isComplete) {
          hasInProgressTool = true;
          currentToolName = tcProcess.toolName || '';
          break;
        }
      }
      if (hasInProgressTool) break;
    }
  }
  
  // Determine final currentTool value:
  // - If tool just failed, clear it immediately
  // - If there's an in-progress tool, show it
  // - Otherwise, clear it
  const finalCurrentTool = justCompletedToolFailed ? '' : (hasInProgressTool ? currentToolName : '');
  
  if (process.env.NODE_ENV === 'development' && justCompletedToolFailed) {
    console.log('[handleSubagentToolCallResult] Tool call failed, clearing currentTool immediately:', {
      taskId,
      toolCallId,
      failedToolName: justCompletedToolName,
      reason: 'Tool call failed, clearing currentTool immediately',
    });
  }
  
  // Update currentTool: clear if tool failed, otherwise use in-progress tool if any
  updateSubagentCard(taskId, {
    messages: updatedMessages,
    currentTool: finalCurrentTool, // Explicitly pass empty string to clear when failed or no tools in progress
  });
  return true;
}

/**
 * Handles message_queued events on per-task SSE streams.
 * Emitted when a follow-up instruction is queued for the running subagent.
 * Inserts a user message bubble with the instruction content.
 * NOT a turn boundary — the subagent keeps its current assistant message streaming.
 *
 * @param {Object} params - Handler parameters
 * @param {string} params.taskId - Task ID (e.g., "task:k7Xm2p")
 * @param {string} params.content - The queued instruction content
 * @param {Object} params.refs - Refs object with subagentStateRefs
 * @param {Function} params.updateSubagentCard - Callback to update subagent card
 * @returns {boolean} True if event was handled
 */
export function handleTaskMessageQueued({ taskId, content, refs, updateSubagentCard }) {
  if (!taskId || !content || !updateSubagentCard) {
    return false;
  }

  const taskRefs = getOrCreateTaskRefs(refs, taskId);
  const updatedMessages = [...taskRefs.messages];

  // Confirm an optimistic pending message if it matches, otherwise insert new one
  const pendingIdx = updatedMessages.findIndex(
    m => m.role === 'user' && m.isPending && m.content === content
  );
  if (pendingIdx !== -1) {
    updatedMessages[pendingIdx] = { ...updatedMessages[pendingIdx], isPending: false };
  } else {
    updatedMessages.push({
      id: `followup-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      role: 'user',
      content,
      contentSegments: [{ type: 'text', content, order: 0 }],
      reasoningProcesses: {},
      toolCallProcesses: {},
    });
  }

  taskRefs.messages = updatedMessages;
  updateSubagentCard(taskId, { messages: updatedMessages });
  return true;
}
