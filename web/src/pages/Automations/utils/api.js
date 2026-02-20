import { api } from '@/api/client';

export const listAutomations = (params) =>
  api.get('/api/v1/automations', { params });

export const getAutomation = (id) =>
  api.get(`/api/v1/automations/${id}`);

export const createAutomation = (data) =>
  api.post('/api/v1/automations', data);

export const updateAutomation = (id, data) =>
  api.patch(`/api/v1/automations/${id}`, data);

export const deleteAutomation = (id) =>
  api.delete(`/api/v1/automations/${id}`);

export const pauseAutomation = (id) =>
  api.post(`/api/v1/automations/${id}/pause`);

export const resumeAutomation = (id) =>
  api.post(`/api/v1/automations/${id}/resume`);

export const triggerAutomation = (id) =>
  api.post(`/api/v1/automations/${id}/trigger`);

export const listExecutions = (id, params) =>
  api.get(`/api/v1/automations/${id}/executions`, { params });

export const listWorkspaces = (params) =>
  api.get('/api/v1/workspaces', { params });
