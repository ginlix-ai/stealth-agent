import { getFlashWorkspace } from '../../ChatAgent/utils/api';

/**
 * Ensures the shared flash workspace exists and returns its workspace_id.
 * @returns {Promise<string>} The flash workspace ID
 */
export async function ensureFlashWorkspace() {
  const flashWs = await getFlashWorkspace();
  return flashWs.workspace_id;
}
