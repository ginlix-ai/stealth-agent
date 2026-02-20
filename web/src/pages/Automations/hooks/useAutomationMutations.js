import { useState, useCallback } from 'react';
import { toast } from '@/components/ui/use-toast';
import * as automationApi from '../utils/api';

export function useAutomationMutations(refetch) {
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (fn, successMsg) => {
    setLoading(true);
    try {
      const result = await fn();
      toast({ title: 'Success', description: successMsg });
      await refetch();
      return result;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Something went wrong';
      toast({ variant: 'destructive', title: 'Error', description: typeof msg === 'string' ? msg : JSON.stringify(msg) });
      throw err;
    } finally {
      setLoading(false);
    }
  }, [refetch]);

  const create = useCallback(
    (data) => run(() => automationApi.createAutomation(data), 'Automation created'),
    [run]
  );

  const update = useCallback(
    (id, data) => run(() => automationApi.updateAutomation(id, data), 'Automation updated'),
    [run]
  );

  const remove = useCallback(
    (id) => run(() => automationApi.deleteAutomation(id), 'Automation deleted'),
    [run]
  );

  const pause = useCallback(
    (id) => run(() => automationApi.pauseAutomation(id), 'Automation paused'),
    [run]
  );

  const resume = useCallback(
    (id) => run(() => automationApi.resumeAutomation(id), 'Automation resumed'),
    [run]
  );

  const trigger = useCallback(
    (id) => run(() => automationApi.triggerAutomation(id), 'Automation triggered'),
    [run]
  );

  return { create, update, remove, pause, resume, trigger, loading };
}
