import { API_BASE_URL } from './config';
import { getToken } from '../auth/tokenStorage';

export const SESSION_INVALID = 'agriroute:session-invalid';
export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status; }
}

export async function apiRequest(path, { token = getToken(), authenticated = true, body, signal, ...options } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = setTimeout(abort, 15000);
  const headers = new Headers(options.headers);
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  if (body !== undefined && !isFormData) headers.set('Content-Type', 'application/json');
  if (authenticated && token) headers.set('Authorization', `Bearer ${token}`);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body), signal: controller.signal });
    if (!response.ok) {
      if (response.status === 401 && authenticated && token) {
        window.dispatchEvent(new CustomEvent(SESSION_INVALID, { detail: { token } }));
      }
      let detail;
      try { detail = (await response.clone().json()).detail; } catch { /* Use the safe status message below. */ }
      const message = typeof detail === 'string' ? detail
        : response.status === 401 ? 'Invalid email or password, or the account is not active.'
        : response.status === 403 ? 'Your account is not allowed to perform this action.'
        : response.status === 404 ? 'The requested AgriRoute record was not found.'
        : response.status === 409 ? 'This action conflicts with the latest AgriRoute data. Refresh and try again.'
        : response.status === 422 ? 'Some submitted values are invalid. Review the form and try again.'
        : response.status === 429 ? 'Too many attempts. Please wait before trying again.'
        : 'AgriRoute could not complete the request. Please try again.';
      throw new ApiError(message, response.status);
    }
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw error;
    throw new ApiError('Unable to reach AgriRoute. Check your connection and that the API is running.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
