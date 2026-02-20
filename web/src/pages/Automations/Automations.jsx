import React, { useState, useCallback } from 'react';
import AutomationsHeader from './components/AutomationsHeader';
import AutomationsTable from './components/AutomationsTable';
import AutomationFormDialog from './components/AutomationFormDialog';
import ConfirmDeleteDialog from './components/ConfirmDeleteDialog';
import { useAutomations } from './hooks/useAutomations';
import { useAutomationMutations } from './hooks/useAutomationMutations';
import './Automations.css';

export default function Automations() {
  const { automations, loading, refetch } = useAutomations();
  const mutations = useAutomationMutations(refetch);

  const [selectedAutomation, setSelectedAutomation] = useState(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingAutomation, setEditingAutomation] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const handleCreateClick = useCallback(() => {
    setEditingAutomation(null);
    setIsFormOpen(true);
  }, []);

  const handleEdit = useCallback((automation) => {
    setSelectedAutomation(null);
    setEditingAutomation(automation);
    setIsFormOpen(true);
  }, []);

  const handleDelete = useCallback((automation) => {
    setSelectedAutomation(null);
    setDeleteTarget(automation);
  }, []);

  const handleFormSubmit = useCallback(async (data) => {
    try {
      if (editingAutomation) {
        await mutations.update(editingAutomation.automation_id, data);
      } else {
        await mutations.create(data);
      }
      setIsFormOpen(false);
      setEditingAutomation(null);
    } catch {
      // error handled by mutations hook
    }
  }, [editingAutomation, mutations]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await mutations.remove(deleteTarget.automation_id);
      setDeleteTarget(null);
    } catch {
      // error handled by mutations hook
    }
  }, [deleteTarget, mutations]);

  const handleSelectAutomation = useCallback((automation) => {
    setSelectedAutomation((prev) =>
      prev?.automation_id === automation.automation_id ? null : automation
    );
  }, []);

  // Keep overlay in sync with fresh data
  const selectedFresh = selectedAutomation
    ? automations.find((a) => a.automation_id === selectedAutomation.automation_id) || selectedAutomation
    : null;

  return (
    <div className="automations-page">
      <AutomationsHeader
        automations={automations}
        onCreateClick={handleCreateClick}
      />

      <div className="automations-card">
        <AutomationsTable
          automations={automations}
          loading={loading}
          selectedAutomation={selectedFresh}
          onSelectAutomation={handleSelectAutomation}
          onCloseOverlay={() => setSelectedAutomation(null)}
          onCreateClick={handleCreateClick}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onPause={mutations.pause}
          onResume={mutations.resume}
          onTrigger={mutations.trigger}
          mutationsLoading={mutations.loading}
        />
      </div>

      <AutomationFormDialog
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        onSubmit={handleFormSubmit}
        automation={editingAutomation}
        loading={mutations.loading}
      />

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        automationName={deleteTarget?.name}
        loading={mutations.loading}
      />
    </div>
  );
}
