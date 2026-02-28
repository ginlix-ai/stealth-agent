/**
 * Shared event utilities for history and streaming event handlers.
 */

/**
 * Normalize old action values to new ones for backward compatibility.
 * Old persisted events may use 'spawned', 'message_queued', 'resumed'.
 */
export function normalizeAction(raw) {
  if (raw === 'spawned') return 'init';
  if (raw === 'message_queued') return 'update';
  if (raw === 'resumed') return 'resume';
  return raw || 'init';
}
