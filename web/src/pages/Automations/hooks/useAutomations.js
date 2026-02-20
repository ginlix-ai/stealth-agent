import { useState, useEffect, useCallback, useRef } from 'react';
import { listAutomations } from '../utils/api';

const POLL_INTERVAL = 30000;

export function useAutomations({ status } = {}) {
  const [automations, setAutomations] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const fetch = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const params = { limit: 100, offset: 0 };
      if (status) params.status = status;
      const { data } = await listAutomations(params);
      setAutomations(data.automations);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  const refetch = useCallback(() => fetch(false), [fetch]);

  useEffect(() => {
    fetch(true);
    intervalRef.current = setInterval(() => fetch(false), POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [fetch]);

  return { automations, total, loading, error, refetch };
}
