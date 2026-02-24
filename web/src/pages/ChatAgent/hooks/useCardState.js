import { useState } from 'react';

/**
 * useCardState Hook
 *
 * Manages state for subagent cards and todo list data.
 * The floating card UI (draggable, minimizable cards) has been removed —
 * subagents render via AgentSidebar + MessageList, and todos via TodoDrawer.
 * This hook still stores card data keyed by cardId for those consumers.
 *
 * @param {Object} initialCards - Initial cards configuration
 * @returns {Object} Cards state and handlers
 */
export function useCardState(initialCards = {}) {
  const [cards, setCards] = useState(initialCards);

  /**
   * Update or create todo list card data.
   * Called when todo list is detected/updated during live streaming.
   * @param {Object} todoData - Todo list data { todos, total, completed, in_progress, pending }
   */
  const updateTodoListCard = (todoData) => {
    const cardId = 'todo-list-card';

    setCards((prev) => {
      if (prev[cardId]) {
        return {
          ...prev,
          [cardId]: {
            ...prev[cardId],
            todoData: todoData,
          },
        };
      } else {
        return {
          ...prev,
          [cardId]: {
            title: 'Todo List',
            todoData: todoData,
          },
        };
      }
    });
  };

  /**
   * Update or create subagent card data.
   * Called when subagent status is detected/updated during live streaming.
   * @param {string} agentId - Stable agent identity (format: "type:uuid", e.g., "research:550e8400-...")
   * @param {Object} subagentDataUpdate - Partial subagent data to merge
   */
  const updateSubagentCard = (agentId, subagentDataUpdate) => {
    const cardId = `subagent-${agentId}`;

    setCards((prev) => {
      if (prev[cardId]) {
        const existingCard = prev[cardId];
        const existingSubagentData = existingCard.subagentData || {};
        const isCurrentlyInactive = existingSubagentData.isActive === false;
        const isBeingReactivated = subagentDataUpdate.isActive === true;

        // Guard: don't overwrite an active card (receiving live updates) with stale
        // history data. This prevents clicking a resumed inline card from replacing
        // the live streaming messages with an old pre-resume snapshot.
        if (!isCurrentlyInactive && subagentDataUpdate.isHistory) {
          if (process.env.NODE_ENV === 'development') {
            console.log('[updateSubagentCard] Skipping history overwrite on active card:', {
              agentId,
              cardId,
              reason: 'Card is active (live streaming) — history push rejected',
            });
          }
          return prev;
        }

        // If card is inactive and not being reactivated, skip pure status updates.
        // However, allow content updates (messages) through — trailing message_chunk
        // and tool_call_result events can arrive after the completion signal due to
        // the tail loop's polling interval.
        const hasContentUpdate = subagentDataUpdate.messages !== undefined;
        if (isCurrentlyInactive && !isBeingReactivated && !hasContentUpdate) {
          if (process.env.NODE_ENV === 'development') {
            console.log('[updateSubagentCard] Skipping update to inactive card:', {
              agentId,
              cardId,
              reason: 'Card is inactive and not being reactivated (no content update)',
            });
          }
          return prev;
        }
        // Compute resolved values before building the card
        let finalMessages = (() => {
          if (subagentDataUpdate.messages === undefined) {
            return existingSubagentData.messages || [];
          }
          // Guard: a fresh streaming accumulator (e.g. after reconnect)
          // starts from [] and builds up incrementally.  Don't let it
          // overwrite a longer existing array until it catches up —
          // otherwise tab-switching during reconnect shows a flash of
          // empty/partial messages.
          const existing = existingSubagentData.messages || [];
          if (existing.length > 0 && subagentDataUpdate.messages.length < existing.length) {
            return existing;
          }
          return subagentDataUpdate.messages;
        })();

        const finalStatus = (() => {
          const newStatus = subagentDataUpdate.status;
          const existingStatus = existingSubagentData.status;

          if (newStatus !== undefined) {
            if (process.env.NODE_ENV === 'development') {
              console.log('[updateSubagentCard] Status update:', {
                agentId,
                newStatus,
                previousStatus: existingStatus,
                willUpdate: newStatus !== existingStatus,
              });
            }
            return newStatus;
          }

          const preservedStatus = existingStatus || 'active';
          if (process.env.NODE_ENV === 'development' && existingStatus === 'completed') {
            console.log('[updateSubagentCard] Preserving completed status:', {
              agentId,
              preservedStatus,
            });
          }
          return preservedStatus;
        })();

        const finalIsActive = subagentDataUpdate.isHistory
          ? false
          : (subagentDataUpdate.isActive !== undefined
            ? subagentDataUpdate.isActive
            : existingSubagentData.isActive !== undefined
              ? existingSubagentData.isActive
              : true);

        // Auto-finalize messages whenever the card is in completed state.
        // This covers both the initial transition AND late tail-loop events
        // that arrive with isStreaming: true after the stream already closed.
        if (finalStatus === 'completed' && finalMessages.length > 0) {
          finalMessages = finalMessages.map(msg => {
            if (msg.role !== 'assistant') return msg;
            const m = { ...msg, isStreaming: false };
            if (m.toolCallProcesses) {
              const procs = { ...m.toolCallProcesses };
              for (const [id, proc] of Object.entries(procs)) {
                if (proc.isInProgress) procs[id] = { ...proc, isInProgress: false, isComplete: true };
              }
              m.toolCallProcesses = procs;
            }
            if (m.reasoningProcesses) {
              const rps = { ...m.reasoningProcesses };
              for (const [id, rp] of Object.entries(rps)) {
                if (rp.isReasoning) rps[id] = { ...rp, isReasoning: false, reasoningComplete: true };
              }
              m.reasoningProcesses = rps;
            }
            return m;
          });
        }

        return {
          ...prev,
          [cardId]: {
            ...existingCard,
            subagentData: {
              ...existingSubagentData,
              ...subagentDataUpdate,
              messages: finalMessages,
              currentTool: subagentDataUpdate.currentTool !== undefined
                ? subagentDataUpdate.currentTool
                : existingSubagentData.currentTool || '',
              status: finalStatus,
              isActive: finalIsActive,
            },
          },
        };
      } else {
        // Don't create new cards for completed/inactive tasks from live streaming
        const isCompletedFromLiveStream = subagentDataUpdate.isActive === false && subagentDataUpdate.isHistory !== true && subagentDataUpdate.isReconnect !== true;

        if (isCompletedFromLiveStream) {
          if (process.env.NODE_ENV === 'development') {
            console.log('[updateSubagentCard] Skipping creation of new card for completed task from live streaming:', {
              agentId,
              cardId,
              reason: 'Completed tasks from live streaming should only update existing cards, not create new ones',
              isActive: subagentDataUpdate.isActive,
              isHistory: subagentDataUpdate.isHistory,
            });
          }
          return prev;
        }

        return {
          ...prev,
          [cardId]: {
            title: subagentDataUpdate.title || 'Subagent',
            subagentData: {
              agentId: agentId,
              taskId: agentId,
              description: '',
              prompt: '',
              type: 'general-purpose',
              toolCalls: 0,
              currentTool: '',
              status: 'active',
              messages: [],
              ...subagentDataUpdate,
              isActive: subagentDataUpdate.isHistory ? false : (subagentDataUpdate.isActive !== undefined ? subagentDataUpdate.isActive : true),
            },
          },
        };
      }
    });
  };

  /**
   * Inactivate all subagent cards.
   * Called at the end of streaming to mark all subagents as inactive.
   */
  const inactivateAllSubagents = () => {
    setCards((prev) => {
      const updated = { ...prev };
      let hasChanges = false;

      Object.keys(updated).forEach((cardId) => {
        if (cardId.startsWith('subagent-') && updated[cardId]?.subagentData) {
          const card = updated[cardId];
          if (card.subagentData.isActive !== false) {
            // Finalize all assistant messages: stop streaming, complete in-progress items
            const msgs = card.subagentData.messages;
            let finalizedMsgs = msgs;
            if (msgs?.length > 0) {
              finalizedMsgs = msgs.map(msg => {
                if (msg.role !== 'assistant') return msg;
                const m = { ...msg, isStreaming: false };
                // Complete in-progress tool calls
                if (m.toolCallProcesses) {
                  const procs = { ...m.toolCallProcesses };
                  for (const [id, proc] of Object.entries(procs)) {
                    if (proc.isInProgress) {
                      procs[id] = { ...proc, isInProgress: false, isComplete: true };
                    }
                  }
                  m.toolCallProcesses = procs;
                }
                // Complete active reasoning
                if (m.reasoningProcesses) {
                  const rps = { ...m.reasoningProcesses };
                  for (const [id, rp] of Object.entries(rps)) {
                    if (rp.isReasoning) {
                      rps[id] = { ...rp, isReasoning: false, reasoningComplete: true };
                    }
                  }
                  m.reasoningProcesses = rps;
                }
                return m;
              });
            }

            updated[cardId] = {
              ...card,
              subagentData: {
                ...card.subagentData,
                isActive: false,
                status: 'completed',
                currentTool: '',
                messages: finalizedMsgs,
              },
            };
            hasChanges = true;
            if (process.env.NODE_ENV === 'development') {
              console.log('[inactivateAllSubagents] Marking subagent as inactive:', {
                taskId: card.subagentData.taskId,
                cardId,
                previousStatus: card.subagentData.status,
              });
            }
          }
        }
      });

      return hasChanges ? updated : prev;
    });
  };

  /**
   * Complete all pending todos in the todo list card.
   * Called at the end of streaming to mark remaining in_progress/pending items as completed.
   */
  const completePendingTodos = () => {
    setCards((prev) => {
      const card = prev['todo-list-card'];
      if (!card?.todoData?.todos) return prev;

      const hasIncomplete = card.todoData.todos.some((t) => t.status !== 'completed');
      if (!hasIncomplete) return prev;

      const completedTodos = card.todoData.todos.map((t) => ({
        ...t,
        status: 'completed',
      }));

      return {
        ...prev,
        'todo-list-card': {
          ...card,
          todoData: {
            ...card.todoData,
            todos: completedTodos,
            completed: card.todoData.total || completedTodos.length,
            in_progress: 0,
            pending: 0,
          },
        },
      };
    });
  };

  /**
   * Remove all subagent cards from state.
   * Called before reconnect to prevent cache + Redis replay overlap (duplicate content).
   */
  const clearSubagentCards = () => {
    setCards((prev) => {
      const cleaned = {};
      Object.entries(prev).forEach(([key, value]) => {
        if (!key.startsWith('subagent-')) {
          cleaned[key] = value;
        }
      });
      return cleaned;
    });
  };

  return {
    cards,
    updateTodoListCard,
    updateSubagentCard,
    inactivateAllSubagents,
    completePendingTodos,
    clearSubagentCards,
  };
}
