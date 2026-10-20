// Prototype strategy: per-tab sessionStorage. Refresh survives; closing the tab
// ends persistence. User identity is never trusted from a cached profile.
const KEY = 'agriroute-access-token';
export function getToken() {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}
export function saveToken(token) { sessionStorage.setItem(KEY, token); }
export function clearToken() {
  try { sessionStorage.removeItem(KEY); } catch { /* No persisted session. */ }
}
