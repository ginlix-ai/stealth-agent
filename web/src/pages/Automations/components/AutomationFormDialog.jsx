import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { listWorkspaces } from '../utils/api';

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Australia/Sydney',
];

const inputStyle = {
  backgroundColor: 'var(--color-bg-card)',
  borderColor: 'var(--color-border-default)',
};

const labelClass = 'text-sm font-medium text-white';
const radioGroupClass = 'flex gap-3';

function RadioOption({ name, value, checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm" style={{ color: 'var(--color-text-secondary)' }}>
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
        className="accent-[#6155F5]"
      />
      {label}
    </label>
  );
}

const INITIAL_FORM = {
  name: '',
  description: '',
  trigger_type: 'cron',
  cron_expression: '',
  timezone: 'UTC',
  next_run_at: '',
  agent_mode: 'flash',
  workspace_id: '',
  instruction: '',
  thread_strategy: 'new',
  max_failures: 3,
};

export default function AutomationFormDialog({ open, onOpenChange, onSubmit, automation, loading }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [workspaces, setWorkspaces] = useState([]);

  const isEdit = !!automation;

  useEffect(() => {
    if (automation) {
      setForm({
        name: automation.name || '',
        description: automation.description || '',
        trigger_type: automation.trigger_type || 'cron',
        cron_expression: automation.cron_expression || '',
        timezone: automation.timezone || 'UTC',
        next_run_at: automation.next_run_at ? automation.next_run_at.slice(0, 16) : '',
        agent_mode: automation.agent_mode || 'flash',
        workspace_id: automation.workspace_id || '',
        instruction: automation.instruction || '',
        thread_strategy: automation.thread_strategy || 'new',
        max_failures: automation.max_failures ?? 3,
      });
    } else {
      setForm(INITIAL_FORM);
    }
  }, [automation, open]);

  useEffect(() => {
    if (open) {
      listWorkspaces({ limit: 100 })
        .then(({ data }) => setWorkspaces(data.workspaces || []))
        .catch(() => {});
    }
  }, [open]);

  const set = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = { ...form };

    if (payload.trigger_type === 'cron') {
      delete payload.next_run_at;
    } else {
      delete payload.cron_expression;
      if (payload.next_run_at) {
        payload.next_run_at = new Date(payload.next_run_at).toISOString();
      }
    }

    if (payload.agent_mode !== 'ptc') {
      delete payload.workspace_id;
    }

    if (!payload.description) delete payload.description;

    payload.max_failures = parseInt(payload.max_failures, 10) || 3;

    onSubmit(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg text-white border overflow-y-auto max-h-[90vh]"
        style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-elevated)' }}
      >
        <DialogHeader>
          <DialogTitle className="text-white">
            {isEdit ? 'Edit Automation' : 'Create Automation'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Name */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <Input
              value={form.name}
              onChange={set('name')}
              placeholder="e.g. Daily market summary"
              required
              className="text-white placeholder:text-gray-500 border"
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Description</label>
            <Input
              value={form.description}
              onChange={set('description')}
              placeholder="Optional description"
              className="text-white placeholder:text-gray-500 border"
              style={inputStyle}
            />
          </div>

          {/* Trigger Type */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Trigger Type</label>
            <div className={radioGroupClass}>
              <RadioOption name="trigger_type" value="cron" checked={form.trigger_type === 'cron'} onChange={set('trigger_type')} label="Cron (recurring)" />
              <RadioOption name="trigger_type" value="once" checked={form.trigger_type === 'once'} onChange={set('trigger_type')} label="Once" />
            </div>
          </div>

          {/* Cron Expression */}
          {form.trigger_type === 'cron' && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Cron Expression</label>
              <Input
                value={form.cron_expression}
                onChange={set('cron_expression')}
                placeholder="*/30 * * * *"
                required
                className="text-white placeholder:text-gray-500 border font-mono"
                style={inputStyle}
              />
              <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                5-field cron: minute hour day-of-month month day-of-week
              </span>
            </div>
          )}

          {/* Run At */}
          {form.trigger_type === 'once' && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Run At</label>
              <Input
                type="datetime-local"
                value={form.next_run_at}
                onChange={set('next_run_at')}
                required
                className="text-white border"
                style={inputStyle}
              />
            </div>
          )}

          {/* Timezone */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Timezone</label>
            <select
              value={form.timezone}
              onChange={set('timezone')}
              className="flex h-10 w-full rounded-md border px-3 py-2 text-sm text-white"
              style={inputStyle}
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>

          {/* Agent Mode */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Agent Mode</label>
            <div className={radioGroupClass}>
              <RadioOption name="agent_mode" value="flash" checked={form.agent_mode === 'flash'} onChange={set('agent_mode')} label="Flash" />
              <RadioOption name="agent_mode" value="ptc" checked={form.agent_mode === 'ptc'} onChange={set('agent_mode')} label="PTC (Sandbox)" />
            </div>
          </div>

          {/* Workspace */}
          {form.agent_mode === 'ptc' && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Workspace</label>
              <select
                value={form.workspace_id}
                onChange={set('workspace_id')}
                required
                className="flex h-10 w-full rounded-md border px-3 py-2 text-sm text-white"
                style={inputStyle}
              >
                <option value="">Select workspace...</option>
                {workspaces.map((ws) => (
                  <option key={ws.workspace_id} value={ws.workspace_id}>
                    {ws.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Instruction */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Instruction</label>
            <Textarea
              value={form.instruction}
              onChange={set('instruction')}
              placeholder="What should the agent do?"
              required
              rows={4}
              className="text-white placeholder:text-gray-500 border"
              style={inputStyle}
            />
          </div>

          {/* Thread Strategy */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Thread Strategy</label>
            <div className={radioGroupClass}>
              <RadioOption name="thread_strategy" value="new" checked={form.thread_strategy === 'new'} onChange={set('thread_strategy')} label="New thread each run" />
              <RadioOption name="thread_strategy" value="continue" checked={form.thread_strategy === 'continue'} onChange={set('thread_strategy')} label="Continue existing" />
            </div>
          </div>

          {/* Max Failures */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Max Failures</label>
            <Input
              type="number"
              min={1}
              max={100}
              value={form.max_failures}
              onChange={set('max_failures')}
              className="text-white border w-24"
              style={inputStyle}
            />
          </div>

          <DialogFooter className="pt-2 gap-2 sm:gap-0">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="text-white"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="text-white"
              style={{ backgroundColor: '#6155F5' }}
            >
              {loading ? 'Saving...' : isEdit ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
