import { createContext, useContext, useMemo } from 'react';

const WorkspaceContext = createContext({ workspaceId: null, downloadFile: null });

export const WorkspaceProvider = ({ workspaceId, downloadFile, children }) => {
  const value = useMemo(() => ({ workspaceId, downloadFile }), [workspaceId, downloadFile]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
};

export const useWorkspaceId = () => useContext(WorkspaceContext).workspaceId;
export const useWorkspaceDownloadFile = () => useContext(WorkspaceContext).downloadFile;
