/**
 * Shared API client for backend REST calls.
 * All portfolio, watchlist, and watchlist-items modules use this.
 */
import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const DEFAULT_USER_ID = 'test_user_001';

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

export function headers(userId = DEFAULT_USER_ID) {
  return { 'X-User-Id': userId };
}
