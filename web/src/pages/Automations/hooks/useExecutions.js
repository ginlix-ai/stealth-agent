import { useState, useEffect, useCallback, useRef } from 'react';
import { listExecutions } from '../utils/api';

const POLL_INTERVAL = 15000;

export function useExecutions(automationId) {
  const [executions, setExecutions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef(null);

  const fetch = useCallback(async (showLoading = false) => {
    if (!automationId) return;
    if (showLoading) setLoading(true);
    try {
      const { data } = await listExecutions(automationId, { limit: 20, offset: 0 });
      setExecutions(data.executions);
      setTotal(data.total);
    } catch {
      // silently fail on polling
    } finally {
      setLoading(false);
    }
  }, [automationId]);

  useEffect(() => {
    if (!automationId) {
      setExecutions([]);
      setTotal(0);
      return;
    }
    fetch(true);
    intervalRef.current = setInterval(() => fetch(false), POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [automationId, fetch]);

  return { executions, total, loading };
}
