import { createContext, useContext } from 'react';

const WorkspaceIdContext = createContext(null);

export const WorkspaceProvider = ({ workspaceId, children }) => (
  <WorkspaceIdContext.Provider value={workspaceId}>{children}</WorkspaceIdContext.Provider>
);

export const useWorkspaceId = () => useContext(WorkspaceIdContext);
