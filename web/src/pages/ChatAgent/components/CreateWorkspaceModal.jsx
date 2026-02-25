import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Upload, FileText, CheckCircle2, Loader2, Circle, AlertCircle } from 'lucide-react';
import { Input } from '../../../components/ui/input';
import { uploadWorkspaceFile } from '../utils/api';
import './CreateWorkspaceModal.css';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * CreateWorkspaceModal — two-phase modal:
 *  Phase 1 (form): name, description, file dropzone
 *  Phase 2 (progress): workspace creation → file uploads → done
 *
 * @param {boolean}  isOpen      - Whether the modal is visible
 * @param {Function} onClose     - Close callback (form phase only)
 * @param {Function} onCreate    - Creates workspace, must return the workspace object
 * @param {Function} onComplete  - Called with workspace_id when everything is finished
 */
function CreateWorkspaceModal({ isOpen, onClose, onCreate, onComplete }) {
  const { t } = useTranslation();
  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [descMode, setDescMode] = useState('agent'); // 'agent' | 'manual'
  const [queuedFiles, setQueuedFiles] = useState([]);
  const [error, setError] = useState(null);

  // Progress state
  const [phase, setPhase] = useState('form'); // 'form' | 'progress'
  const [creationStep, setCreationStep] = useState('creating'); // 'creating' | 'uploading' | 'done' | 'error'
  const [fileStatuses, setFileStatuses] = useState({}); // { [name]: 'pending'|'uploading'|'done'|'failed' }
  const [currentUploadProgress, setCurrentUploadProgress] = useState(0);
  const [currentUploadName, setCurrentUploadName] = useState('');
  const [createdWorkspace, setCreatedWorkspace] = useState(null);
  const [progressError, setProgressError] = useState(null);

  // Drag state
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef(null);

  // ---- File queue helpers ----

  const addFiles = useCallback((fileList) => {
    const incoming = Array.from(fileList);
    setError(null);

    const oversized = incoming.filter((f) => f.size > MAX_FILE_SIZE);
    if (oversized.length > 0) {
      setError(`${oversized.map((f) => f.name).join(', ')} ${t('workspace.exceedsLimit')}`);
    }

    const valid = incoming.filter((f) => f.size <= MAX_FILE_SIZE);
    setQueuedFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const deduped = valid.filter((f) => !existingNames.has(f.name));
      return [...prev, ...deduped];
    });
  }, []);

  const removeFile = useCallback((fileName) => {
    setQueuedFiles((prev) => prev.filter((f) => f.name !== fileName));
  }, []);

  // ---- Drag-and-drop handlers ----

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (dragCounter.current === 1) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files?.length) {
      addFiles(e.dataTransfer.files);
    }
  };

  // ---- Submit ----

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(t('workspace.workspaceNameRequired'));
      return;
    }

    setPhase('progress');
    setCreationStep('creating');
    setProgressError(null);

    let workspace;
    try {
      workspace = await onCreate({
        name: name.trim(),
        description: descMode === 'manual' ? description.trim() : '',
      });
      setCreatedWorkspace(workspace);
    } catch (err) {
      setCreationStep('error');
      setProgressError(err.message || t('workspace.failedCreateWorkspace'));
      return;
    }

    // Upload queued files
    if (queuedFiles.length > 0) {
      setCreationStep('uploading');
      const statuses = {};
      queuedFiles.forEach((f) => { statuses[f.name] = 'pending'; });
      setFileStatuses({ ...statuses });

      for (const file of queuedFiles) {
        setCurrentUploadName(file.name);
        setCurrentUploadProgress(0);
        setFileStatuses((prev) => ({ ...prev, [file.name]: 'uploading' }));

        try {
          await uploadWorkspaceFile(workspace.workspace_id, file, null, (pct) => {
            setCurrentUploadProgress(pct);
          });
          setFileStatuses((prev) => ({ ...prev, [file.name]: 'done' }));
        } catch {
          setFileStatuses((prev) => ({ ...prev, [file.name]: 'failed' }));
        }
      }
    }

    setCreationStep('done');
  };

  // ---- Retry (after error) ----

  const handleRetry = () => {
    if (createdWorkspace) {
      // Workspace already created, retry uploads
      retryUploads(createdWorkspace);
    } else {
      // Retry from scratch
      handleSubmit(new Event('submit'));
    }
  };

  const retryUploads = async (workspace) => {
    setCreationStep('uploading');
    setProgressError(null);

    const statuses = {};
    queuedFiles.forEach((f) => { statuses[f.name] = 'pending'; });
    setFileStatuses({ ...statuses });

    for (const file of queuedFiles) {
      setCurrentUploadName(file.name);
      setCurrentUploadProgress(0);
      setFileStatuses((prev) => ({ ...prev, [file.name]: 'uploading' }));

      try {
        await uploadWorkspaceFile(workspace.workspace_id, file, null, (pct) => {
          setCurrentUploadProgress(pct);
        });
        setFileStatuses((prev) => ({ ...prev, [file.name]: 'done' }));
      } catch {
        setFileStatuses((prev) => ({ ...prev, [file.name]: 'failed' }));
      }
    }

    setCreationStep('done');
  };

  // ---- Reset & close ----

  const resetAndClose = () => {
    setName('');
    setDescription('');
    setDescMode('agent');
    setQueuedFiles([]);
    setError(null);
    setPhase('form');
    setCreationStep('creating');
    setFileStatuses({});
    setCurrentUploadProgress(0);
    setCurrentUploadName('');
    setCreatedWorkspace(null);
    setProgressError(null);
    onClose();
  };

  const handleOpenWorkspace = () => {
    const wsId = createdWorkspace?.workspace_id;
    resetAndClose();
    if (wsId && onComplete) onComplete(wsId);
  };

  // ---- Computed ----

  const isInProgress = phase === 'progress' && (creationStep === 'creating' || creationStep === 'uploading');
  const canClose = !isInProgress;

  const failedCount = Object.values(fileStatuses).filter((s) => s === 'failed').length;
  const doneCount = Object.values(fileStatuses).filter((s) => s === 'done').length;

  if (!isOpen) return null;

  // =========== PROGRESS PHASE ===========
  if (phase === 'progress') {
    return (
      <div className="cwm-overlay">
        <div className="cwm-modal" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="cwm-header">
            <h2 className="cwm-title">
              {creationStep === 'done' ? t('workspace.workspaceReady') : t('workspace.creatingWorkspace')}
            </h2>
            {canClose && (
              <button className="cwm-close-btn" onClick={handleOpenWorkspace}>
                <X className="h-5 w-5" />
              </button>
            )}
          </div>

          <div className="cwm-progress">
            {/* Steps */}
            <div className="cwm-steps">
              {/* Step 1: Initialize */}
              <StepRow
                label={t('workspace.initializingWorkspace')}
                status={
                  creationStep === 'creating' ? 'active'
                    : creationStep === 'error' && !createdWorkspace ? 'error'
                      : 'done'
                }
              />

              {/* Step 2: Upload (only if files queued) */}
              {queuedFiles.length > 0 && (
                <StepRow
                  label={t('workspace.uploadingFiles')}
                  status={
                    creationStep === 'uploading' ? 'active'
                      : creationStep === 'done' ? (failedCount > 0 ? 'error' : 'done')
                        : creationStep === 'creating' ? 'pending'
                          : creationStep === 'error' && createdWorkspace ? 'error'
                            : 'pending'
                  }
                />
              )}

              {/* Step 3: Ready */}
              <StepRow
                label={t('workspace.ready')}
                status={creationStep === 'done' ? 'done' : 'pending'}
              />
            </div>

            {/* Per-file progress during uploading */}
            {creationStep === 'uploading' && (
              <div className="cwm-upload-detail">
                {queuedFiles.map((file) => {
                  const status = fileStatuses[file.name] || 'pending';
                  const isCurrentlyUploading = status === 'uploading' && currentUploadName === file.name;
                  return (
                    <div key={file.name}>
                      <div className="cwm-upload-file-row">
                        <FileText className="h-4 w-4 cwm-file-icon" />
                        <span className="cwm-upload-file-name">{file.name}</span>
                        <span className={`cwm-upload-file-status cwm-upload-file-status--${status}`}>
                          {status === 'done' ? t('common.done') : status === 'failed' ? t('common.failed') : status === 'uploading' ? `${currentUploadProgress}%` : ''}
                        </span>
                      </div>
                      {isCurrentlyUploading && (
                        <div className="cwm-progress-bar" style={{ marginTop: 4 }}>
                          <div className="cwm-progress-bar-fill" style={{ width: `${currentUploadProgress}%` }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Done summary */}
            {creationStep === 'done' && queuedFiles.length > 0 && (
              <div className="cwm-done-summary">
                <div className="cwm-done-subtitle">
                  {doneCount} file{doneCount !== 1 ? 's' : ''} uploaded
                  {failedCount > 0 && ` · ${failedCount} failed`}
                </div>
              </div>
            )}

            {/* Error */}
            {creationStep === 'error' && progressError && (
              <div className="cwm-error-box">{progressError}</div>
            )}

            {/* Action buttons */}
            <div className="cwm-actions">
              {creationStep === 'done' && (
                <button className="cwm-btn-create" onClick={handleOpenWorkspace}>
                  {t('workspace.openWorkspace')}
                </button>
              )}
              {creationStep === 'error' && (
                <>
                  <button className="cwm-btn-cancel" onClick={resetAndClose}>{t('common.cancel')}</button>
                  <button className="cwm-btn-create" onClick={handleRetry}>{t('common.retry')}</button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========== FORM PHASE ===========
  return (
    <div className="cwm-overlay" onClick={resetAndClose}>
      <div className="cwm-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="cwm-header">
          <h2 className="cwm-title">{t('workspace.createNewWorkspace')}</h2>
          <button className="cwm-close-btn" onClick={resetAndClose}>
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Name */}
          <div className="cwm-field">
            <label className="cwm-label">
              {t('workspace.workspaceName')} <span className="cwm-label-required">*</span>
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('workspace.enterWorkspaceName')}
              className="w-full"
              style={{
                backgroundColor: 'var(--color-bg-card)',
                border: '1px solid var(--color-border-muted)',
                color: 'var(--color-text-primary)',
              }}
              autoFocus
            />
          </div>

          {/* Description mode toggle */}
          <div className="cwm-field">
            <label className="cwm-label">
              {t('common.description')} <span className="cwm-label-optional">{t('common.optional')}</span>
            </label>
            <div className="cwm-toggle-group">
              <button
                type="button"
                className={`cwm-toggle-btn ${descMode === 'agent' ? 'cwm-toggle-btn--active' : ''}`}
                onClick={() => { setDescMode('agent'); setDescription(''); }}
              >
                {t('workspace.descModeAgent')}
              </button>
              <button
                type="button"
                className={`cwm-toggle-btn ${descMode === 'manual' ? 'cwm-toggle-btn--active' : ''}`}
                onClick={() => setDescMode('manual')}
              >
                {t('workspace.descModeManual')}
              </button>
            </div>
            {descMode === 'manual' ? (
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('workspace.enterWorkspaceDesc')}
                rows={3}
                className="cwm-textarea"
                style={{ marginTop: 8 }}
              />
            ) : (
              <div className="cwm-toggle-hint">{t('workspace.descModeAgentHint')}</div>
            )}
          </div>

          {/* File dropzone */}
          <div className="cwm-dropzone-wrapper">
            <div className="cwm-dropzone-label">{t('workspace.files')} <span className="cwm-label-optional">{t('common.optional')}</span></div>
            <div className="cwm-dropzone-sublabel">{t('workspace.filesUploadNote')}</div>
            <div
              className={`cwm-dropzone ${isDragging ? 'cwm-dropzone-active' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <Upload className="h-6 w-6 cwm-dropzone-icon" />
              <div className="cwm-dropzone-text">
                {t('workspace.dragFilesHere')}<span>{t('workspace.clickToBrowse')}</span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files?.length) addFiles(e.target.files);
                  e.target.value = '';
                }}
              />
            </div>

            {/* Queued files */}
            {queuedFiles.length > 0 && (
              <div className="cwm-file-list">
                {queuedFiles.map((file) => (
                  <div key={file.name} className="cwm-file-item">
                    <FileText className="h-4 w-4 cwm-file-icon" />
                    <span className="cwm-file-name">{file.name}</span>
                    <span className="cwm-file-size">{formatFileSize(file.size)}</span>
                    <button
                      type="button"
                      className="cwm-file-remove"
                      onClick={() => removeFile(file.name)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Error */}
          {error && <div className="cwm-error">{error}</div>}

          {/* Actions */}
          <div className="cwm-actions">
            <button type="button" className="cwm-btn-cancel" onClick={resetAndClose}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="cwm-btn-create" disabled={!name.trim()}>
              {t('common.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Step indicator row for the progress phase
 */
function StepRow({ label, status }) {
  let icon;
  let iconClass = '';
  let labelClass = '';

  switch (status) {
    case 'done':
      icon = <CheckCircle2 className="h-5 w-5" />;
      iconClass = 'cwm-step-icon--done';
      break;
    case 'active':
      icon = <Loader2 className="h-5 w-5 animate-spin" />;
      iconClass = 'cwm-step-icon--active';
      break;
    case 'error':
      icon = <AlertCircle className="h-5 w-5" />;
      iconClass = 'cwm-step-icon--error';
      break;
    default:
      icon = <Circle className="h-5 w-5" />;
      iconClass = 'cwm-step-icon--pending';
      labelClass = 'cwm-step-label--pending';
  }

  return (
    <div className="cwm-step">
      <div className={`cwm-step-icon ${iconClass}`}>{icon}</div>
      <span className={`cwm-step-label ${labelClass}`}>{label}</span>
    </div>
  );
}

export default CreateWorkspaceModal;
